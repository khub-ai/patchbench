"""
generate.py — Build leaderboard.json and leaderboard.md from submitted results.

Run after merging a new PR that adds a result JSON:
  python leaderboard/generate.py

Output:
  leaderboard/leaderboard.json   machine-readable
  leaderboard/leaderboard.md     human-readable table (rendered on GitHub)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_HERE    = Path(__file__).resolve().parent
_ROOT    = _HERE.parent
_RESULTS = _ROOT / "results"

VERDICT_COLOUR = {"go": "🟢", "partial": "🟡", "no-go": "🔴"}

# Source dataset links per domain — shown in the leaderboard table and data sources section.
DOMAIN_DATASET = {
    "road_surface": {
        "name":    "RSCD",
        "url":     "https://github.com/ztsrxh/RSCD-Road_Surface_Classification_Dataset",
        "credit":  "Tsinghua University",
        "license": "CC BY-NC-SA 4.0",
    },
    "birds": {
        "name":    "CUB-200-2011",
        "url":     "https://www.vision.caltech.edu/datasets/cub_200_2011/",
        "credit":  "Caltech",
        "license": "Research use",
    },
    "dermatology": {
        "name":    "HAM10000",
        "url":     "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T",
        "credit":  "ViDIR Group, Medical University of Vienna",
        "license": "CC BY-NC-SA 4.0",
    },
}


def _fmt(value, fmt=".2f") -> str:
    """Format a score or return 'N/A' if None."""
    if value is None:
        return "N/A"
    return format(value, fmt)


def _sort_key(r: dict):
    """Sort: measured perception descending, then unmeasured, then model name."""
    p = r["perception"]
    return (0 if p is None else -p, r["model"])


def collect_results() -> list:
    rows = []
    for json_path in sorted(_RESULTS.glob("**/*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            rows.append({
                "model":              data["pupil_model"],
                "domain":             json_path.parts[-3],
                "pair_id":            json_path.parts[-2],
                "benchmark_id":       data["benchmark_id"],
                "benchmark_version":  data["benchmark_version"],
                "verdict":            data["verdict"],
                "perception":         data.get("perception_score"),
                "vocab_overlap":      data.get("vocabulary_overlap"),
                "zero_shot":          data["zero_shot_accuracy"],
                "rule_aided":         data["rule_aided_accuracy"],
                "rule_delta":         data["rule_comprehension_delta"],
                "consistency":        data.get("consistency_score"),
                "total_cost_usd":     data["total_cost_usd"],
                "submitted":          data["submitted"],
                "result_file":        str(json_path.relative_to(_ROOT)),
                "notes":              data.get("notes", ""),
            })
        except Exception as e:
            print(f"  Warning: could not parse {json_path}: {e}")
    return sorted(rows, key=_sort_key)


def write_json(rows: list) -> None:
    out = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_results": len(rows),
        "results":   rows,
    }
    path = _HERE / "leaderboard.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"  Written: {path.name}")


def write_markdown(rows: list) -> None:
    lines = [
        "# PatchBench Leaderboard",
        "",
        f"> Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')} · "
        f"{len(rows)} result(s)",
        "",
        "Sorted by perception score descending. "
        "See [CONTRIBUTING.md](../CONTRIBUTING.md) to submit your model's results.",
        "",
        "| Verdict | Model | Domain | Pair | Percep. | VocabΔ | ZeroShot | RuleDelta | Consist. |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        v    = VERDICT_COLOUR.get(r["verdict"], r["verdict"])
        pair = r["pair_id"].replace("_", " ")
        note = " ⚠" if r.get("notes") else ""

        # Link domain name to its source dataset
        ds = DOMAIN_DATASET.get(r["domain"])
        if ds:
            domain_cell = f"[{r['domain']}]({ds['url']})"
        else:
            domain_cell = r["domain"]

        lines.append(
            f"| {v} {r['verdict']}{note} "
            f"| `{r['model']}` "
            f"| {domain_cell} "
            f"| {pair} "
            f"| {_fmt(r['perception'])} "
            f"| {_fmt(r['vocab_overlap'])} "
            f"| {r['zero_shot']:.2f} "
            f"| {r['rule_delta']:+.2f} "
            f"| {_fmt(r['consistency'])} |"
        )

    lines += [
        "",
        "## Column definitions",
        "",
        "| Column | Description |",
        "|---|---|",
        "| Percep. | Feature detection accuracy (PUPIL vs VALIDATOR ground truth) |",
        "| VocabΔ | Vocabulary overlap with expert descriptions |",
        "| ZeroShot | Classification accuracy without rules injected |",
        "| RuleDelta | Accuracy gain from rule injection (higher = more patchable) |",
        "| Consist. | Fraction of images where repeated runs give the same answer |",
        "",
        "## Verdict thresholds",
        "",
        "| Verdict | Condition |",
        "|---|---|",
        "| 🟢 go | Percep ≥ 0.60 AND RuleDelta ≥ 0.15 AND Consist ≥ 0.75 |",
        "| 🟡 partial | Above no-go floors but not all go thresholds met |",
        "| 🔴 no-go | Percep < 0.30 OR Consist < 0.50 |",
        "",
        "> ⚠ Results with N/A scores were derived from pre-manifest DD session data "
        "(Steps 2 and 3 not run). "
        "RuleDelta and ZeroShot are from expanded validation runs; "
        "Percep, VocabΔ, and Consist were not measured. "
        "These results demonstrate DD effectiveness but cannot produce a full patchability verdict.",
        "",
        "---",
        "",
        "## Image data sources",
        "",
        "Benchmark images are curated subsets from publicly available datasets.",
        "See [DATA_LICENSE.md](../DATA_LICENSE.md) for full attribution and license text.",
        "",
        "| Domain | Dataset | Credit | License |",
        "|---|---|---|---|",
    ]

    # Emit one row per domain in DOMAIN_DATASET.
    # Mark as "images pending" only when the benchmarks/<domain>/ directory does not exist.
    benchmarks_dir = _ROOT / "benchmarks"
    for domain, ds in DOMAIN_DATASET.items():
        has_images = (benchmarks_dir / domain).is_dir()
        marker = "" if has_images else " *(images pending)*"
        lines.append(
            f"| {domain}{marker} "
            f"| [{ds['name']}]({ds['url']}) "
            f"| {ds['credit']} "
            f"| {ds['license']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Research context",
        "",
        "PatchBench measures **Dialogic Distillation (DD)** patchability — "
        "whether a small VLM can be improved by injecting expert-authored visual "
        "rules at inference time, without any retraining.",
        "",
        "| Resource | Link |",
        "|---|---|",
        "| Benchmark repo | [khub-ai/patchbench](https://github.com/khub-ai/patchbench) |",
        "| DD research system | [khub-ai/khub-knowledge-fabric](https://github.com/khub-ai/khub-knowledge-fabric) |",
        "| Probe design | [docs/probe_design.md](../docs/probe_design.md) |",
        "| Patchability theory | [docs/patchability.md](../docs/patchability.md) |",
        "| How to contribute | [CONTRIBUTING.md](../CONTRIBUTING.md) |",
    ]

    path = _HERE / "leaderboard.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Written: {path.name}")


if __name__ == "__main__":
    print("Collecting results...")
    rows = collect_results()
    print(f"  Found {len(rows)} result(s)")
    write_json(rows)
    write_markdown(rows)
    print("Done.")
