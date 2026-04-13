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
from datetime import datetime
from pathlib import Path

_HERE    = Path(__file__).resolve().parent
_ROOT    = _HERE.parent
_RESULTS = _ROOT / "results"

VERDICT_COLOUR = {"go": "🟢", "partial": "🟡", "no-go": "🔴"}


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
                "perception":         data["perception_score"],
                "vocab_overlap":      data["vocabulary_overlap"],
                "zero_shot":          data["zero_shot_accuracy"],
                "rule_aided":         data["rule_aided_accuracy"],
                "rule_delta":         data["rule_comprehension_delta"],
                "consistency":        data["consistency_score"],
                "total_cost_usd":     data["total_cost_usd"],
                "submitted":          data["submitted"],
                "result_file":        str(json_path.relative_to(_ROOT)),
            })
        except Exception as e:
            print(f"  Warning: could not parse {json_path}: {e}")
    return sorted(rows, key=lambda r: (-r["perception"], r["model"]))


def write_json(rows: list) -> None:
    out = {
        "generated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
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
        f"> Generated {datetime.utcnow().strftime('%Y-%m-%d')} · "
        f"{len(rows)} result(s)",
        "",
        "Sorted by perception score descending. "
        "See [CONTRIBUTING.md](../CONTRIBUTING.md) to add your model.",
        "",
        "| Verdict | Model | Domain | Pair | Percep. | VocabΔ | ZeroShot | RuleDelta | Consist. |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        v    = VERDICT_COLOUR.get(r["verdict"], r["verdict"])
        pair = r["pair_id"].replace("_", " ")
        lines.append(
            f"| {v} {r['verdict']} "
            f"| `{r['model']}` "
            f"| {r['domain']} "
            f"| {pair} "
            f"| {r['perception']:.2f} "
            f"| {r['vocab_overlap']:.2f} "
            f"| {r['zero_shot']:.2f} "
            f"| {r['rule_delta']:+.2f} "
            f"| {r['consistency']:.2f} |"
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
