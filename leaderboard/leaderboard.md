# PatchBench Leaderboard

> Generated 2026-04-13 · 2 result(s)

Sorted by perception score descending. See [CONTRIBUTING.md](../CONTRIBUTING.md) to add your model.

| Verdict | Model | Domain | Pair | Percep. | VocabΔ | ZeroShot | RuleDelta | Consist. |
|---|---|---|---|---|---|---|---|---|
| 🟡 partial ⚠ | `qwen/qwen3-vl-8b-instruct` | birds | bronzed vs shiny cowbird | N/A | N/A | 0.33 | +0.50 | N/A |
| 🟡 partial ⚠ | `qwen/qwen3-vl-8b-instruct` | dermatology | melanoma vs nevus | N/A | N/A | 0.55 | +0.22 | N/A |

## Column definitions

| Column | Description |
|---|---|
| Percep. | Feature detection accuracy (PUPIL vs VALIDATOR ground truth) |
| VocabΔ | Vocabulary overlap with expert descriptions |
| ZeroShot | Classification accuracy without rules injected |
| RuleDelta | Accuracy gain from rule injection (higher = more patchable) |
| Consist. | Fraction of images where repeated runs give the same answer |

## Verdict thresholds

| Verdict | Condition |
|---|---|
| 🟢 go | Percep ≥ 0.60 AND RuleDelta ≥ 0.15 AND Consist ≥ 0.75 |
| 🟡 partial | Above no-go floors but not all go thresholds met |
| 🔴 no-go | Percep < 0.30 OR Consist < 0.50 |

> ⚠ Results with N/A scores were derived from pre-manifest DD session data (Steps 2 and 3 not run). RuleDelta and ZeroShot are from expanded validation runs; Percep, VocabΔ, and Consist were not measured. These results demonstrate DD effectiveness but cannot produce a full patchability verdict.