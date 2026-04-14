"""
PatchBench probe runner — tests whether a VLM can be patched with expert rules.

Four steps assess the PUPIL model's capability for a given domain:
  1. Expert vocabulary      — does PUPIL describe domain features spontaneously?
  2. Feature detection      — can PUPIL find specific features when queried?
  3. Rule comprehension     — does injecting a rule improve PUPIL accuracy?
     3a. Zero-shot sweep to find failures
     3b. Failure-driven rule generation (TUTOR, grounded in descriptions)
     3c. Rule quality gate (VALIDATOR classifies held-out subset with rules)
     3d. Rule-aided sweep (PUPIL with per-class rules)
  4. Consistency            — does PUPIL give stable answers on the same image?

TUTOR and VALIDATOR outputs for Steps 1–3 ground truth are pre-committed in
the benchmark manifest — contributors only need API credentials for their own
PUPIL model.  Pass --recompute-tutor to regenerate those outputs from scratch.

Verdict:
  go      — PUPIL is a good DD candidate for this domain
  partial — DD may work with simpler rule phrasing
  no-go   — PUPIL lacks the perceptual capability for this domain

Usage:
  python runner/probe.py \\
      --benchmark benchmarks/road_surface/dry_vs_wet/probe_v1/manifest.json \\
      --pupil-model qwen/qwen3-vl-8b-instruct

  python runner/probe.py --list-benchmarks
  python runner/probe.py --benchmark ... --recompute-tutor
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import pickle
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .schema import (
    BenchmarkManifest, ManifestImage, FeatureQuery, Precomputed,
    ProbeResult, VERDICT_GO, VERDICT_PARTIAL, VERDICT_NO_GO,
    DIFFICULTY_EASY, DIFFICULTY_MEDIUM, DIFFICULTY_HARD,
)
from .models import ModelCaller, image_block

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent

# ---------------------------------------------------------------------------
# Verdict thresholds
# ---------------------------------------------------------------------------

_GO_PERCEPTION_MIN         = 0.60
_GO_RULE_COMPREHENSION_MIN = 0.15
_GO_CONSISTENCY_MIN        = 0.75
_NOGO_PERCEPTION_MAX       = 0.30
_NOGO_CONSISTENCY_MAX      = 0.50
_CONSISTENCY_REPEATS       = 3
_CONSISTENCY_N_IMAGES      = 5
_MAX_CONCURRENT            = 5   # semaphore cap for PUPIL calls
_RULE_GATE_N_PER_CLASS     = 3   # held-out images per class for rule quality gate
_RULE_GATE_MIN_ACCURACY    = 0.75 # VALIDATOR must reach this on gate images for rules to pass


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

_PRICING: Dict[str, Tuple[float, float]] = {
    # (input $/1M, output $/1M)
    "claude-opus":   (15.00, 75.00),
    "claude-sonnet": ( 3.00, 15.00),
    "claude-haiku":  ( 0.80,  4.00),
    "qwen":          ( 0.10,  0.15),
    "llama":         ( 0.88,  0.88),
    "llava":         ( 0.10,  0.15),
    "mistral":       ( 0.40,  1.20),
    "gemma":         ( 0.10,  0.20),
}

def _estimate_cost(model: str, inp: int, out: int) -> float:
    for key, (ip, op) in _PRICING.items():
        if key in model.lower():
            return (inp * ip + out * op) / 1_000_000
    return 0.0


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _parse_json_object(text: str) -> Optional[dict]:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    start = text.find("{")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if esc: esc = False; continue
        if ch == "\\" and in_str: esc = True; continue
        if ch == '"': in_str = not in_str; continue
        if in_str: continue
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try: return json.loads(text[start:i+1])
                except Exception: pass
                break
    return None


def _parse_json_array(text: str) -> Optional[list]:
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        try:
            r = json.loads(m.group(1))
            if isinstance(r, list): return r
        except Exception:
            pass
    start = text.find("[")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if esc: esc = False; continue
        if ch == "\\" and in_str: esc = True; continue
        if ch == '"': in_str = not in_str; continue
        if in_str: continue
        if ch == "[": depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    r = json.loads(text[start:i+1])
                    if isinstance(r, list): return r
                except Exception: pass
                break
    return None


# ---------------------------------------------------------------------------
# Cache (memory + optional disk)
# ---------------------------------------------------------------------------

_MEM_CACHE: Dict[str, str] = {}


def _cache_key(model: str, role: str, img_hash: str, prompt_hash: str) -> str:
    raw = f"{model}\x00{role}\x00{img_hash}\x00{prompt_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_get(key: str, cache_dir: Optional[Path]) -> Optional[str]:
    if key in _MEM_CACHE:
        return _MEM_CACHE[key]
    if cache_dir:
        p = cache_dir / f"{key}.pkl"
        if p.exists():
            try:
                v = pickle.loads(p.read_bytes())
                _MEM_CACHE[key] = v
                return v
            except Exception:
                pass
    return None


def _cache_put(key: str, value: str, cache_dir: Optional[Path]) -> None:
    _MEM_CACHE[key] = value
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            (cache_dir / f"{key}.pkl").write_bytes(pickle.dumps(value))
        except Exception:
            pass


def clear_cache(disk: bool = False, cache_dir: Optional[Path] = None) -> None:
    _MEM_CACHE.clear()
    if disk and cache_dir and cache_dir.exists():
        for f in cache_dir.glob("*.pkl"):
            f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Bounded concurrency
# ---------------------------------------------------------------------------

async def _bounded_gather(coros, max_concurrent: int = _MAX_CONCURRENT):
    sem = asyncio.Semaphore(max_concurrent)
    async def _wrap(c):
        async with sem:
            return await c
    return list(await asyncio.gather(*[_wrap(c) for c in coros]))


# ---------------------------------------------------------------------------
# Core LLM call wrapper
# ---------------------------------------------------------------------------

async def _call(
    caller:     ModelCaller,
    role:       str,
    model:      str,
    system:     str,
    content:    list,
    max_tokens: int,
    cache:      bool = True,
    img_hash:   str  = "",
    cache_dir:  Optional[Path] = None,
    costs:      Optional[dict] = None,
) -> str:
    text_parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
    p_hash = hashlib.sha256((system + "".join(text_parts)).encode()).hexdigest()[:16]

    if cache:
        key = _cache_key(model, role, img_hash, p_hash)
        cached = _cache_get(key, cache_dir)
        if cached is not None:
            return cached

    text, usage = await caller.call(model, system, content, max_tokens)

    inp = usage.get("input_tokens", len("".join(text_parts)) // 4)
    out = usage.get("output_tokens", len(text) // 4)
    if costs is not None:
        r = costs.setdefault(role, {"input_tokens": 0, "output_tokens": 0,
                                     "api_calls": 0, "cost_usd": 0.0})
        r["input_tokens"]  += inp
        r["output_tokens"] += out
        r["api_calls"]     += 1
        r["cost_usd"]      += _estimate_cost(model, inp, out)

    if cache:
        _cache_put(key, text, cache_dir)
    return text


# ---------------------------------------------------------------------------
# Step 1 — TUTOR descriptions (served from precomputed or regenerated)
# ---------------------------------------------------------------------------

async def _get_tutor_descriptions(
    manifest:    BenchmarkManifest,
    manifest_path: Path,
    caller:      ModelCaller,
    tutor_model: str,
    recompute:   bool,
    cache_dir:   Optional[Path],
    costs:       dict,
    _print,
) -> Tuple[Dict[str, str], List[FeatureQuery], Dict[str, Dict[str, bool]], Dict[str, dict]]:
    """Returns (tutor_descs, feature_queries, validator_answers, seed_rules).

    seed_rules maps class name -> rule dict, one entry per class.
    Rules are grounded in sampled TUTOR descriptions rather than generated
    from class names alone.
    """

    if not recompute and manifest.has_precomputed:
        pc = manifest.precomputed
        _print(f"  [dim]Using pre-committed TUTOR/VALIDATOR outputs "
               f"({pc.tutor_model}, {pc.validator_model})[/dim]")
        # Prefer seed_rules (per-class dict); fall back to legacy seed_rule (single).
        if pc.seed_rules:
            seed_rules = pc.seed_rules
        elif pc.seed_rule:
            favored = pc.seed_rule.get("favors", manifest.class_a)
            seed_rules = {favored: pc.seed_rule}
        else:
            seed_rules = {}
        return (
            pc.tutor_descriptions,
            pc.feature_queries,
            pc.validator_answers,
            seed_rules,
        )

    _print("  Regenerating TUTOR descriptions and feature queries...")
    class_a = manifest.class_a
    class_b = manifest.class_b

    # TUTOR descriptions
    tutor_descs = {}
    for img in manifest.images:
        img_path = manifest.image_path(img, manifest_path)
        system = (
            f"You are an expert visual analyst. "
            f"Describe images using precise domain vocabulary."
        )
        content = [
            image_block(img_path),
            {"type": "text", "text": (
                f"Describe this image as an expert would, focusing on "
                f"observable visual features that distinguish "
                f"'{class_a}' from '{class_b}'. "
                f"Ground truth: {img.true_class}. "
                f"3–5 sentences. Be specific about textures, reflectivity, "
                f"patterns, and surface properties."
            )},
        ]
        h = hashlib.md5(img_path.read_bytes()).hexdigest()
        desc = await _call(caller, "TUTOR", tutor_model, system, content,
                           512, True, h, cache_dir, costs)
        tutor_descs[img.image_id] = desc

    # Feature queries
    anchor_img = manifest.images[0]
    anchor_path = manifest.image_path(anchor_img, manifest_path)
    anchor_hash = hashlib.md5(anchor_path.read_bytes()).hexdigest()

    system = "You are a domain expert designing a vision model capability test."
    fq_content = [{"type": "text", "text": (
        f"Generate 12 yes/no feature detection queries for distinguishing "
        f"'{class_a}' from '{class_b}'.\n\n"
        f"Cover difficulty levels:\n"
        f"  easy (4):   broad, unambiguous features\n"
        f"  medium (4): moderate, requiring some domain knowledge\n"
        f"  hard (4):   subtle, requiring expert vocabulary\n\n"
        f"Each query: a yes/no question answerable from a single image.\n\n"
        f"Respond with JSON array:\n"
        f'[{{"feature_id": "snake_case", "question": "Is there...?", '
        f'"diagnostic_for": "{class_a}" or "{class_b}", '
        f'"difficulty": "easy"|"medium"|"hard"}}, ...]'
    )}]
    raw = await _call(caller, "TUTOR", tutor_model, system, fq_content,
                      2048, True, anchor_hash + "_queries", cache_dir, costs)
    parsed = _parse_json_array(raw) or []
    feature_queries = [
        FeatureQuery(
            feature_id     = q.get("feature_id", f"feature_{i}"),
            question       = q.get("question", ""),
            diagnostic_for = q.get("diagnostic_for", class_a),
            difficulty     = q.get("difficulty", DIFFICULTY_MEDIUM),
        )
        for i, q in enumerate(parsed) if isinstance(q, dict)
    ][:12]

    # VALIDATOR ground truth for feature queries
    validator_model = manifest.precomputed.validator_model if manifest.precomputed else tutor_model
    validator_answers: Dict[str, Dict[str, bool]] = {}
    for img in manifest.images[:10]:
        img_path = manifest.image_path(img, manifest_path)
        img_hash = hashlib.md5(img_path.read_bytes()).hexdigest()
        validator_answers[img.image_id] = {}
        for q in feature_queries:
            system_v = "You are an expert visual analyst."
            content_v = [
                image_block(img_path),
                {"type": "text", "text": (
                    f"Question: {q.question}\n\n"
                    f'Respond: {{"answer": "yes" or "no", "observation": "what you see"}}'
                )},
            ]
            raw_v = await _call(caller, "VALIDATOR", validator_model, system_v,
                                content_v, 128, True,
                                img_hash + "_" + q.feature_id, cache_dir, costs)
            result = _parse_json_object(raw_v) or {}
            validator_answers[img.image_id][q.feature_id] = (
                result.get("answer", "").lower().startswith("y")
            )

    # Seed rules — one per class, grounded in TUTOR descriptions.
    # Sample up to 3 descriptions per class to keep the prompt concise.
    imgs_a = [img for img in manifest.images if img.true_class == class_a][:3]
    imgs_b = [img for img in manifest.images if img.true_class == class_b][:3]
    sample_descs = "\n\n".join(
        [f"[{class_a}] {tutor_descs[img.image_id]}" for img in imgs_a if img.image_id in tutor_descs] +
        [f"[{class_b}] {tutor_descs[img.image_id]}" for img in imgs_b if img.image_id in tutor_descs]
    )
    seed_rules = {}
    for favored, other in [(class_a, class_b), (class_b, class_a)]:
        seed_content = [{"type": "text", "text": (
            f"Here are expert descriptions of images from this dataset:\n\n"
            f"{sample_descs}\n\n"
            f"Write one concise classification rule for identifying '{favored}' "
            f"(as opposed to '{other}') based only on visual features observable "
            f"in images like those above.\n"
            f'JSON: {{"rule": "...", "preconditions": ["..."], "favors": "{favored}"}}'
        )}]
        raw_rule = await _call(caller, "TUTOR", tutor_model, system,
                               seed_content, 512, True,
                               anchor_hash + f"_seed_rule_{favored}", cache_dir, costs)
        parsed = _parse_json_object(raw_rule)
        if parsed:
            seed_rules[favored] = parsed

    return tutor_descs, feature_queries, validator_answers, seed_rules


# ---------------------------------------------------------------------------
# Steps 2–4 — PUPIL only (never cached)
# ---------------------------------------------------------------------------

async def _pupil_vocab_overlap(
    img: ManifestImage,
    img_path: Path,
    tutor_desc: str,
    caller: ModelCaller,
    pupil_model: str,
    validator_model: str,
    costs: dict,
    cache_dir: Optional[Path],
) -> float:
    # PUPIL free description
    raw = await _call(
        caller, "PUPIL", pupil_model,
        "You are a visual analysis assistant.",
        [image_block(img_path),
         {"type": "text", "text": "Describe what you see in this image in detail."}],
        512, False, "", cache_dir, costs,
    )
    # VALIDATOR scores overlap (cached — same expert desc + PUPIL desc = same score)
    img_hash = hashlib.md5((tutor_desc + raw).encode()).hexdigest()
    overlap_raw = await _call(
        caller, "VALIDATOR", validator_model,
        "You are an objective evaluator.",
        [{"type": "text", "text": (
            f"EXPERT: {tutor_desc}\n\nMODEL: {raw}\n\n"
            f"Score vocabulary overlap 0.0–1.0 (0=generic, 1=expert terms used).\n"
            f'JSON: {{"score": 0.0-1.0, "reason": "brief"}}'
        )}],
        128, True, img_hash, cache_dir, costs,
    )
    result = _parse_json_object(overlap_raw) or {}
    if "score" in result:
        return float(result["score"])
    m = re.search(r'\b(0\.\d+|1\.0)\b', overlap_raw)
    return float(m.group()) if m else 0.0


async def _pupil_feature_detection(
    img: ManifestImage,
    img_path: Path,
    query: FeatureQuery,
    validator_gt: bool,
    caller: ModelCaller,
    pupil_model: str,
    costs: dict,
) -> bool:
    raw = await _call(
        caller, "PUPIL", pupil_model,
        "You are a visual analysis assistant. Answer questions precisely.",
        [image_block(img_path),
         {"type": "text", "text": (
             f"Question: {query.question}\n\n"
             f'JSON: {{"answer": "yes" or "no", "observation": "brief"}}'
         )}],
        128, False, "", None, costs,
    )
    result = _parse_json_object(raw) or {}
    pupil_ans = result.get("answer", "").lower().startswith("y") if result else "yes" in raw.lower()
    return pupil_ans == validator_gt


async def _classify(
    img: ManifestImage,
    img_path: Path,
    class_a: str,
    class_b: str,
    caller: ModelCaller,
    pupil_model: str,
    costs: dict,
    rule: Optional[dict] = None,
    caller_role: str = "PUPIL",
) -> str:
    if rule:
        preconds = "\n".join(f"  - {p}" for p in rule.get("preconditions", []))
        extra = (
            f"\n\nCLASSIFICATION RULE: {rule.get('rule', '')}\n"
            f"PRECONDITIONS (must all be met):\n{preconds}\n\n"
            f"Apply the rule if preconditions are met; otherwise use your best judgment."
        )
    else:
        extra = ""
    raw = await _call(
        caller, caller_role, pupil_model,
        "You are a visual classification assistant.",
        [image_block(img_path),
         {"type": "text", "text": (
             f"Classify this image as:\n  A) {class_a}\n  B) {class_b}"
             f"{extra}\n\n"
             f'JSON: {{"classification": "{class_a}" or "{class_b}", "reasoning": "brief"}}'
         )}],
        256, False, "", None, costs,
    )
    result = _parse_json_object(raw) or {}
    c = result.get("classification", raw)
    if class_a.lower() in c.lower(): return class_a
    if class_b.lower() in c.lower(): return class_b
    return class_a if "A" in c else class_b


# ---------------------------------------------------------------------------
# Write precomputed outputs back to manifest
# ---------------------------------------------------------------------------

def _write_precomputed_to_manifest(
    manifest_path:   Path,
    tutor_model:     str,
    validator_model: str,
    tutor_descs:     Dict[str, str],
    feature_queries: list,
    validator_answers: Dict[str, Dict[str, bool]],
    seed_rules:      Dict[str, dict],
) -> None:
    """Persist TUTOR/VALIDATOR outputs into the manifest's precomputed section.

    Safe to call multiple times — merges into existing precomputed data so that
    a partial run (e.g. interrupted after Step 1) can be resumed.
    """
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    pc = data.setdefault("precomputed", {})
    pc["tutor_model"]        = tutor_model
    pc["validator_model"]    = validator_model
    pc["generated"]          = time.strftime("%Y-%m-%d")
    pc["tutor_descriptions"] = tutor_descs
    pc["feature_queries"]    = [
        {
            "feature_id":     q.feature_id,
            "question":       q.question,
            "diagnostic_for": q.diagnostic_for,
            "difficulty":     q.difficulty,
        }
        for q in feature_queries
    ]
    pc["validator_answers"]  = validator_answers
    pc["seed_rules"]         = seed_rules
    manifest_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Rule quality gate
# ---------------------------------------------------------------------------

async def _validate_rules_gate(
    rules:           Dict[str, dict],
    manifest:        BenchmarkManifest,
    manifest_path:   Path,
    caller:          ModelCaller,
    validator_model: str,
    costs:           dict,
    n_per_class:     int = _RULE_GATE_N_PER_CLASS,
) -> Tuple[float, bool]:
    """Validate generated rules using the VALIDATOR on a held-out image subset.

    Uses the last n_per_class images per class (distinct from the first-3 used
    in seed rule generation) to check that rule text is actually discriminative
    before attributing a low PUPIL delta to poor rule-following ability.

    Returns (gate_accuracy, gate_passed).
    """
    if not rules:
        return 0.0, False

    gate_images: List[ManifestImage] = []
    for cls in (manifest.class_a, manifest.class_b):
        cls_imgs = [img for img in manifest.images if img.true_class == cls]
        gate_images.extend(cls_imgs[-n_per_class:] if len(cls_imgs) >= n_per_class else cls_imgs)

    if not gate_images:
        return 0.0, False

    results = await _bounded_gather([
        _classify(
            img, manifest.image_path(img, manifest_path),
            manifest.class_a, manifest.class_b,
            caller, validator_model, costs,
            rules.get(img.true_class),
            caller_role="VALIDATOR",
        )
        for img in gate_images
    ])

    correct  = sum(p == img.true_class for img, p in zip(gate_images, results))
    accuracy = correct / len(gate_images)
    passed   = accuracy >= _RULE_GATE_MIN_ACCURACY
    return round(accuracy, 4), passed


# ---------------------------------------------------------------------------
# Main probe entry point
# ---------------------------------------------------------------------------

async def run_probe(
    manifest_path:    str | Path,
    pupil_model:      str,
    tutor_model:      str  = "claude-opus-4-6",
    validator_model:  str  = "claude-sonnet-4-6",
    recompute_tutor:  bool = False,
    save_precomputed: bool = False,
    anthropic_key:    str  = "",
    openrouter_key:   str  = "",
    cache_dir:        Optional[Path] = None,
    console          = None,
) -> ProbeResult:
    """Run the full PatchBench probe. Returns a ProbeResult."""

    manifest_path = Path(manifest_path)
    manifest      = BenchmarkManifest.load(manifest_path)
    caller        = ModelCaller(anthropic_key, openrouter_key)
    costs: dict   = {}

    _print = console.print if console else print

    _print(f"\n[bold]PatchBench Probe[/bold]")
    _print(f"  PUPIL:      {pupil_model}")
    _print(f"  Benchmark:  {manifest.benchmark_id}  ({manifest.n_images} images)")
    _print(f"  Pair:       {manifest.class_a} vs {manifest.class_b}")

    # ------------------------------------------------------------------
    # TUTOR/VALIDATOR outputs
    # ------------------------------------------------------------------
    _print("\n  [bold]Step 1/4[/bold] Expert descriptions + feature queries...")
    tutor_descs, feature_queries, validator_answers, seed_rules = (
        await _get_tutor_descriptions(
            manifest, manifest_path, caller, tutor_model,
            recompute_tutor or save_precomputed, cache_dir, costs, _print,
        )
    )
    _print(f"    {len(tutor_descs)} descriptions, {len(feature_queries)} feature queries")

    if save_precomputed:
        _write_precomputed_to_manifest(
            manifest_path, tutor_model, validator_model,
            tutor_descs, feature_queries, validator_answers, seed_rules,
        )
        _print(f"  [green]Precomputed outputs saved to manifest.[/green]")

    # ------------------------------------------------------------------
    # Step 2 — PUPIL vocabulary
    # ------------------------------------------------------------------
    _print("  [bold]Step 2/4[/bold] PUPIL vocabulary probe...")
    vocab_scores = []
    for img in manifest.images:
        img_path    = manifest.image_path(img, manifest_path)
        tutor_desc  = tutor_descs.get(img.image_id, "")
        score = await _pupil_vocab_overlap(
            img, img_path, tutor_desc, caller,
            pupil_model, validator_model, costs, cache_dir,
        )
        vocab_scores.append(score)
    vocabulary_overlap = sum(vocab_scores) / len(vocab_scores) if vocab_scores else 0.0
    _print(f"    Vocabulary overlap: {vocabulary_overlap:.3f}")

    # ------------------------------------------------------------------
    # Step 3 — Feature detection
    # ------------------------------------------------------------------
    _print("  [bold]Step 3/4[/bold] Feature detection probe...")
    query_images = manifest.images[:10]
    feature_results: Dict[str, List[bool]] = {}

    for query in feature_queries:
        results = []
        for img in query_images:
            img_path  = manifest.image_path(img, manifest_path)
            gt        = validator_answers.get(img.image_id, {}).get(query.feature_id, False)
            correct   = await _pupil_feature_detection(
                img, img_path, query, gt, caller, pupil_model, costs,
            )
            results.append(correct)
        feature_results[f"{query.feature_id}_{query.difficulty}"] = results

    feature_profile = {
        k: round(sum(v) / len(v), 4) if v else 0.0
        for k, v in feature_results.items()
    }
    avg_by_diff: Dict[str, Optional[float]] = {}
    for diff in (DIFFICULTY_EASY, DIFFICULTY_MEDIUM, DIFFICULTY_HARD):
        scores = [v for k, v in feature_profile.items() if k.endswith(f"_{diff}")]
        avg_by_diff[diff] = round(sum(scores) / len(scores), 4) if scores else None

    perception_score = sum(feature_profile.values()) / len(feature_profile) if feature_profile else 0.0
    _print(f"    Easy: {avg_by_diff.get('easy')}  "
           f"Medium: {avg_by_diff.get('medium')}  "
           f"Hard: {avg_by_diff.get('hard')}  "
           f"Overall: {perception_score:.3f}")

    # ------------------------------------------------------------------
    # Step 4 — Rule comprehension delta + consistency
    # ------------------------------------------------------------------
    _print("  [bold]Step 4/4[/bold] Rule comprehension + consistency...")
    class_a = manifest.class_a
    class_b = manifest.class_b

    # 4a: Zero-shot sweep first.
    zs_results = await _bounded_gather([
        _classify(img, manifest.image_path(img, manifest_path),
                  class_a, class_b, caller, pupil_model, costs)
        for img in manifest.images
    ])
    zs_correct = sum(p == img.true_class for img, p in zip(manifest.images, zs_results))
    n = len(manifest.images)
    zero_shot_acc = zs_correct / n if n else 0.0

    # 4b: Generate failure-driven rules from zero-shot errors, then run rule-aided.
    # For each misclassified image, ask TUTOR to refine the seed rule for that class
    # using the TUTOR description as grounding. Collect one rule per class.
    failures = [
        (img, pred) for img, pred in zip(manifest.images, zs_results)
        if pred != img.true_class
    ]
    failure_rules = dict(seed_rules)  # start from seed rules as fallback
    if failures:
        for true_class in (class_a, class_b):
            class_failures = [(img, pred) for img, pred in failures
                              if img.true_class == true_class][:3]
            if not class_failures:
                continue
            other_class = class_b if true_class == class_a else class_a
            failure_descs = "\n\n".join(
                f"[Misclassified as {pred}; correct: {true_class}]\n"
                f"{tutor_descs.get(img.image_id, '')}"
                for img, pred in class_failures
            )
            refine_content = [{"type": "text", "text": (
                f"A vision model misclassified the following '{true_class}' images "
                f"as '{other_class}':\n\n{failure_descs}\n\n"
                f"Write one concise classification rule that would help correctly "
                f"identify '{true_class}' (vs '{other_class}') based on the visual "
                f"features described above.\n"
                f'JSON: {{"rule": "...", "preconditions": ["..."], "favors": "{true_class}"}}'
            )}]
            fail_hash = hashlib.md5(failure_descs.encode()).hexdigest()
            raw = await _call(caller, "TUTOR", tutor_model,
                              "You are a domain expert designing visual classification rules.",
                              refine_content, 512, True,
                              fail_hash + f"_failure_rule_{true_class}", cache_dir, costs)
            parsed = _parse_json_object(raw)
            if parsed:
                failure_rules[true_class] = parsed

    # 4c: Rule quality gate — VALIDATOR classifies a held-out subset with rules.
    # Confirms rule text is discriminative before attributing any PUPIL delta
    # (or lack thereof) to the model's rule-following ability.
    gate_acc, gate_passed = await _validate_rules_gate(
        failure_rules, manifest, manifest_path,
        caller, validator_model, costs,
    )

    # Apply per-image rule: use the rule that favors the correct class.
    ra_results = await _bounded_gather([
        _classify(img, manifest.image_path(img, manifest_path),
                  class_a, class_b, caller, pupil_model, costs,
                  failure_rules.get(img.true_class))
        for img in manifest.images
    ]) if failure_rules else zs_results

    ra_correct = sum(p == img.true_class for img, p in zip(manifest.images, ra_results))
    rule_aided_acc = ra_correct / n if n else 0.0
    delta          = rule_aided_acc - zero_shot_acc

    # Consistency
    subset = manifest.images[:_CONSISTENCY_N_IMAGES]
    consistent = 0
    for img in subset:
        img_path = manifest.image_path(img, manifest_path)
        preds = [
            await _classify(img, img_path, class_a, class_b, caller, pupil_model, costs)
            for _ in range(_CONSISTENCY_REPEATS)
        ]
        if len(set(preds)) == 1:
            consistent += 1
    consistency_score = consistent / len(subset) if subset else 0.0

    gate_label = "[passed]" if gate_passed else "[WARN: weak rules]"
    _print(f"    Zero-shot: {zero_shot_acc:.3f}  Rule-aided: {rule_aided_acc:.3f}  "
           f"Delta: {delta:+.3f}  Consistency: {consistency_score:.3f}")
    _print(f"    Rule gate: {gate_acc:.3f} {gate_label}")

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    weak_points, recommendations = [], []

    if perception_score < _NOGO_PERCEPTION_MAX:
        weak_points.append(
            f"Perception score {perception_score:.2f} below {_NOGO_PERCEPTION_MAX} "
            f"— PUPIL cannot describe domain features"
        )
    if consistency_score < _NOGO_CONSISTENCY_MAX:
        weak_points.append(
            f"Consistency score {consistency_score:.2f} below {_NOGO_CONSISTENCY_MAX} "
            f"— PUPIL responses are unstable on this domain"
        )
    if weak_points:
        verdict = VERDICT_NO_GO
        recommendations.append(
            "Try a PUPIL model with a stronger visual backbone, "
            "or fine-tune the visual encoder on domain images."
        )
    elif (perception_score >= _GO_PERCEPTION_MIN
          and delta >= _GO_RULE_COMPREHENSION_MIN
          and consistency_score >= _GO_CONSISTENCY_MIN):
        verdict = VERDICT_GO
    else:
        verdict = VERDICT_PARTIAL
        if perception_score < _GO_PERCEPTION_MIN:
            recommendations.append("Use simpler, coarser rule vocabulary for this PUPIL.")
        if delta < _GO_RULE_COMPREHENSION_MIN:
            recommendations.append("Rule injection not improving accuracy — try shorter, "
                                    "more directive rule phrasing.")
        if consistency_score < _GO_CONSISTENCY_MIN:
            recommendations.append("Use temperature=0 for PUPIL calls if available.")

    colour = {"go": "green", "partial": "yellow", "no-go": "red"}[verdict]
    _print(f"\n  Verdict: [{colour}][bold]{verdict.upper()}[/bold][/{colour}]")

    total_cost = sum(v["cost_usd"] for v in costs.values())
    _print(f"  Cost: ${total_cost:.4f}")

    return ProbeResult(
        benchmark_id             = manifest.benchmark_id,
        benchmark_version        = manifest.version,
        schema_version           = "1.0",
        submitted                = time.strftime("%Y-%m-%dT%H:%M:%S"),
        pupil_model              = pupil_model,
        tutor_model              = tutor_model,
        validator_model          = validator_model,
        verdict                  = verdict,
        perception_score         = round(perception_score, 4),
        vocabulary_overlap       = round(vocabulary_overlap, 4),
        zero_shot_accuracy       = round(zero_shot_acc, 4),
        rule_aided_accuracy      = round(rule_aided_acc, 4),
        rule_comprehension_delta = round(delta, 4),
        consistency_score        = round(consistency_score, 4),
        rule_gate_accuracy       = gate_acc,
        rule_gate_passed         = gate_passed,
        feature_detection_by_difficulty = avg_by_diff,
        feature_profile          = feature_profile,
        weak_points              = weak_points,
        recommendations          = recommendations,
        costs                    = costs,
        total_cost_usd           = round(total_cost, 6),
        per_image_zero_shot      = [
            {"image_id": img.image_id, "true": img.true_class, "predicted": p}
            for img, p in zip(manifest.images, zs_results)
        ],
        per_image_rule_aided     = [
            {"image_id": img.image_id, "true": img.true_class, "predicted": p}
            for img, p in zip(manifest.images, ra_results)
        ],
    )
