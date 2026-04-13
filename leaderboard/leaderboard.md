# PatchBench Leaderboard

> Generated 2026-04-13 · 2 result(s)

Sorted by perception score descending. See [CONTRIBUTING.md](../CONTRIBUTING.md) to submit your model's results.

| Verdict | Model | Domain | Confusable pair | Percep. | VocabΔ | ZeroShot | RuleDelta | Consist. |
|---|---|---|---|---|---|---|---|---|
| 🟡 partial ⚠ | `qwen/qwen3-vl-8b-instruct` | [birds](https://www.vision.caltech.edu/datasets/cub_200_2011/) | [bronzed vs shiny cowbird](https://github.com/khub-ai/khub-knowledge-fabric/tree/main/usecases/image-classification/birds) | N/A | N/A | 0.33 | +0.50 | N/A |
| 🟡 partial ⚠ | `qwen/qwen3-vl-8b-instruct` | [dermatology](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T) | [melanoma vs nevus](https://github.com/khub-ai/khub-knowledge-fabric/tree/main/usecases/image-classification/dermatology) | N/A | N/A | 0.55 | +0.22 | N/A |

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

---

## Image data sources

Benchmark images are curated subsets from publicly available datasets.
See [DATA_LICENSE.md](../DATA_LICENSE.md) for full attribution and license text.

| Domain | Dataset | Credit | License |
|---|---|---|---|
| road_surface | [RSCD](https://github.com/ztsrxh/RSCD-Road_Surface_Classification_Dataset) | Tsinghua University | CC BY-NC-SA 4.0 |
| birds *(images pending)* | [CUB-200-2011](https://www.vision.caltech.edu/datasets/cub_200_2011/) | Caltech | Research use |
| dermatology *(images pending)* | [HAM10000](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T) | ViDIR Group, Medical University of Vienna | CC BY-NC-SA 4.0 |

---

## Research context

PatchBench measures **Dialogic Distillation (DD)** patchability — whether a small VLM can be improved by injecting expert-authored visual rules at inference time, without any retraining.

| Resource | Link |
|---|---|
| Benchmark repo | [khub-ai/patchbench](https://github.com/khub-ai/patchbench) |
| DD research system | [khub-ai/khub-knowledge-fabric](https://github.com/khub-ai/khub-knowledge-fabric) |
| Probe design | [docs/probe_design.md](../docs/probe_design.md) |
| Patchability theory | [docs/patchability.md](../docs/patchability.md) |
| How to contribute | [CONTRIBUTING.md](../CONTRIBUTING.md) |