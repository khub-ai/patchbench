# Probe Design: How PatchBench Measures VLM Patchability

> This document describes the design of the PatchBench probe — why it is
> structured this way, what each step measures, and how the verdict is derived.
> For usage instructions, see [getting_started.md](getting_started.md).
>
> The authoritative research implementation lives in the
> [KHub Knowledge Fabric](https://github.com/khub-ai/khub-knowledge-fabric)
> at `core/dialogic_distillation/probe.py`. The PatchBench runner
> (`runner/probe.py`) is a self-contained public adaptation of that code.

---

## The Problem Being Solved

Dialogic Distillation (DD) improves a small VLM by injecting expert-authored
visual rules at inference time — no retraining required. But DD only works if
the PUPIL model has latent visual capability that the rules can unlock.

Two failure modes look identical from the outside (DD doesn't improve accuracy)
but have completely different causes:

| Failure mode | Cause | Remedy |
|---|---|---|
| **Vocabulary gap** | PUPIL can see features but lacks the terms | DD — inject expert vocabulary |
| **Perception barrier** | PUPIL physically cannot perceive the features | Different model or modality |
| **Comprehension failure** | PUPIL sees features but ignores the rule text | Simpler rule phrasing |
| **Instability** | PUPIL gives random answers on the same image | Model unsuitable for domain |

Running a full DD session to discover a perception barrier wastes time and
API cost. The probe diagnoses capability *before* DD begins.

> **The probe answers: "Is this PUPIL in the right regime for DD to work here?"**

---

## The Four-Step Structure

The probe has four steps. Steps 1–3 ground truth (TUTOR descriptions, feature
queries, VALIDATOR answers) are **pre-committed** in the benchmark manifest —
contributors only pay for their own PUPIL model calls. Steps 1–3 can also be
regenerated from scratch with `--recompute-tutor`.

### Step 1 — Expert Descriptions + Feature Queries  *(TUTOR + VALIDATOR, cached)*

**What happens**: The TUTOR model (Claude Opus) describes each probe image in
domain-specific expert vocabulary. It then generates 12 yes/no feature
detection queries covering easy → medium → hard difficulty. The VALIDATOR
model (Claude Sonnet) independently answers each query on each image to
establish ground truth.

**Why this step exists**: The TUTOR descriptions define the vocabulary space
that DD rules will use. The feature queries operationalise "can the PUPIL see
what expert rules refer to?" into testable binary questions. The VALIDATOR
answers give us ground truth without relying on the image labels alone.

**What is cached**: Everything in this step. Changing the PUPIL model does not
re-run TUTOR or VALIDATOR — they are served from the pre-committed manifest
or from disk cache.

---

### Step 2 — PUPIL Vocabulary Probe  *(PUPIL + VALIDATOR scoring, PUPIL not cached)*

**What happens**: The PUPIL is shown each image with a free-description prompt
("describe what you see in detail"). Its response is compared to the TUTOR's
description by the VALIDATOR, which scores vocabulary overlap 0–1.

**Why this step exists**: Low overlap (< 0.20) means the PUPIL uses generic
language ("grey road") while the expert uses domain-specific language
("uniform specular sheen with no visible aggregate texture"). This gap is
*exactly what DD exploits* — but only if the PUPIL can actually perceive the
features when directed to. This step measures the spontaneous vocabulary gap.

**Output**: `vocabulary_overlap` — not used in the verdict directly, but
diagnostic. High vocabulary gap + high perception score = ideal DD candidate.

---

### Step 3 — Feature Detection  *(PUPIL only, not cached)*

**What happens**: The PUPIL is asked each of the 12 TUTOR-generated yes/no
questions on 10 of the probe images. Its answers are compared to the
pre-committed VALIDATOR ground truth. Per-feature detection rates are computed,
aggregated by difficulty.

**Why this step exists**: This is the core of the probe. It directly answers
"can this specific PUPIL model observe the specific features that expert rules
will refer to?" — which the DD grounding check (which uses the VALIDATOR, not
the PUPIL) cannot answer. A VALIDATOR observing a feature does not mean the
PUPIL can.

The easy → hard gradient is important: a model that fails easy features has a
genuine perception barrier. A model that fails only hard features may still be
patchable with simplified rule vocabulary.

**Output**: `perception_score` (overall), `feature_detection_by_difficulty`
(per difficulty tier), `feature_profile` (per-feature).

---

### Step 4 — Rule Comprehension Delta + Consistency  *(PUPIL only, not cached)*

**What happens — comprehension delta**: The PUPIL classifies all probe images
twice — once with no rule (zero-shot), once with the seed rule injected into
the prompt. The accuracy difference is the rule comprehension delta.

**Why**: A positive delta proves that injecting expert vocabulary actually
changes the PUPIL's behaviour. This is the mechanism DD relies on. A
near-zero delta means the PUPIL ignores injected instructions — DD will
produce well-crafted rules that make no difference.

**What happens — consistency**: The PUPIL is run 3 times on the same 5 images
with the same prompt. The fraction of images where all 3 runs agree is the
consistency score.

**Why**: A highly inconsistent PUPIL is essentially sampling randomly. Even
perfectly written rules cannot fix random sampling. Consistency < 0.50 is a
hard no-go regardless of other scores.

**Output**: `zero_shot_accuracy`, `rule_aided_accuracy`,
`rule_comprehension_delta`, `consistency_score`.

---

## Verdict Logic

Three scores determine the verdict:

```
perception_score         — from Step 3
rule_comprehension_delta — from Step 4
consistency_score        — from Step 4
```

Decision tree:

```
if perception_score < 0.30 OR consistency_score < 0.50:
    verdict = "no-go"       ← hard floors: perception barrier or instability

elif (perception_score   >= 0.60 AND
      rule_delta         >= 0.15 AND
      consistency_score  >= 0.75):
    verdict = "go"          ← all three dimensions cleared

else:
    verdict = "partial"     ← above no-go floors but not all go thresholds met
```

| Dimension | no-go floor | go threshold |
|---|---|---|
| Perception score | < 0.30 | ≥ 0.60 |
| Rule comprehension delta | — | ≥ +0.15 |
| Consistency | < 0.50 | ≥ 0.75 |

**Interpreting partial**: The report's `weak_points` and `recommendations`
fields identify which dimension fell short and what to try. Common partial
patterns:

| Pattern | Likely cause | Recommendation |
|---|---|---|
| Low perception, passes floors | Hard vocabulary gap (PUPIL needs prompting) | Try simpler, coarser rule vocabulary |
| Low rule delta, good perception | PUPIL ignores long/complex instructions | Shorter, more directive rules |
| Low consistency only | High sampling temperature | Use temperature=0 if available |
| Fails easy features | Genuine perception barrier | Try larger model |

---

## Pre-Committed TUTOR/VALIDATOR Outputs

The `precomputed` section of each manifest contains:

```json
{
  "tutor_model":         "claude-opus-4-6",
  "validator_model":     "claude-sonnet-4-6",
  "generated":           "2026-04-13",
  "tutor_descriptions":  {"image_id": "expert description..."},
  "feature_queries":     [{"feature_id": "...", "question": "...", ...}],
  "validator_answers":   {"image_id": {"feature_id": true/false, ...}},
  "seed_rule":           {"rule": "...", "preconditions": [...]}
}
```

When this section is populated, contributors need zero TUTOR/VALIDATOR API
calls. The runner reads these values directly from the manifest.

**The precomputed section in the current `probe_v1` manifest is an empty
skeleton** — `tutor_descriptions`, `feature_queries`, and `validator_answers`
are all empty dicts/lists. To populate it, a maintainer must run:

```bash
python run_probe.py \
    --pupil-model any/model \
    --recompute-tutor \
    --tutor-model claude-opus-4-6 \
    --validator-model claude-sonnet-4-6
```

Then copy the TUTOR/VALIDATOR outputs from the result JSON back into the
manifest's `precomputed` section and commit. This is a **one-time setup cost**
of ~$0.15. After that, all future contributors get these for free.

---

## Cache Layers

The runner maintains two cache layers for TUTOR/VALIDATOR calls:

1. **In-memory** (`_MEM_CACHE`) — persists within a Python process
2. **Disk cache** (`--cache-dir`, default `.cache/probe/`) — pickled responses,
   keyed on `sha256(model + role + image_md5 + prompt_hash)`

PUPIL calls are **never cached** — fresh responses are required to measure the
actual model capability at test time.

Clear cache:
```bash
python run_probe.py --clear-cache
```

---

## Cost Profile

For a standard 24-image probe run:

| Role | API calls | Typical cost | Cached after? |
|---|---|---|---|
| TUTOR (Claude Opus) | 25 | ~$0.10 | Yes — pre-committed |
| VALIDATOR (Claude Sonnet) | 122 | ~$0.05 | Yes — pre-committed |
| PUPIL (Qwen3-VL-8B) | ~175 | ~$0.01 | Never |
| **Total (first contributor)** | | **~$0.01** | |
| **Total (subsequent contributors)** | | **~$0.01** | |

Once precomputed outputs are committed, TUTOR and VALIDATOR costs are $0 for
all subsequent contributors.

---

## Schema Versioning

The manifest schema version (`schema_version` field) follows semantic versioning:

- **Patch** (1.0.x): no structural changes, only content additions (new images,
  updated precomputed outputs)
- **Minor** (1.x.0): new optional fields added; old runners still work
- **Major** (x.0.0): breaking structural change; old result JSONs incompatible

Result JSONs reference both `benchmark_version` (the manifest version they were
run against) and `schema_version` (the runner version). This allows the
leaderboard to flag results generated against different manifest versions.

---

## Open Questions

1. **Optimal image count**: 24 (12/class) gives adequate statistical power for
   the feature detection step but ±10pp uncertainty on rule comprehension delta.
   v2 manifests may expand to 30/class.

2. **Seed rule quality sensitivity**: The rule comprehension delta depends on
   the seed rule. The pre-committed seed rule is generated by the TUTOR without
   seeing any failure cases — it is a generic discriminating rule, not a
   DD-optimised rule. A seed rule from a real DD session would give a higher and
   more meaningful delta measurement.

3. **Temperature control**: Consistency scores are sensitive to sampling
   temperature. Results for the same model at different temperatures are not
   directly comparable. Consider standardising on temperature=0 where the API
   allows it.

4. **Cross-domain correlation**: Do models that score `go` on road surface also
   score `go` on dermatology? Preliminary expectation is no — domain-specific
   perceptual capability matters. Collecting results across domains will allow
   this to be tested empirically.
