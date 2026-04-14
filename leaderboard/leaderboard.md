# PatchBench Leaderboard

> Generated 2026-04-14 · 13 result(s)

Sorted by perception score descending. See [CONTRIBUTING.md](../CONTRIBUTING.md) to submit your model's results.

| Verdict | Model | Domain | Confusable pair | Percep. | VocabΔ | ZeroShot | RuleDelta | Consist. |
|---|---|---|---|---|---|---|---|---|
| 🟡 partial | `google/gemma-4-26b-a4b-it` | [road_surface](https://github.com/ztsrxh/RSCD-Road_Surface_Classification_Dataset) | [dry vs wet](https://github.com/khub-ai/patchbench/tree/main/benchmarks/road_surface/dry_vs_wet) | 0.86 | 0.30 | 0.58 | +0.08 | 0.80 |
| 🟢 go | `google/gemma-4-26b-a4b-it` | [dermatology](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T) | [melanoma vs nevus](https://github.com/khub-ai/patchbench/tree/main/benchmarks/dermatology/melanoma_vs_nevus) | 0.81 | 0.32 | 0.67 | +0.33 | 1.00 |
| 🔴 no-go | `openai/gpt-4o` | [dermatology](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T) | [melanoma vs nevus](https://github.com/khub-ai/patchbench/tree/main/benchmarks/dermatology/melanoma_vs_nevus) | 0.81 | 0.22 | 0.79 | +0.04 | 0.40 |
| 🟢 go | `claude-haiku-4-5-20251001` | [dermatology](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T) | [melanoma vs nevus](https://github.com/khub-ai/patchbench/tree/main/benchmarks/dermatology/melanoma_vs_nevus) | 0.78 | 0.32 | 0.54 | +0.21 | 1.00 |
| 🟢 go | `qwen/qwen3-vl-8b-instruct` | [road_surface](https://github.com/ztsrxh/RSCD-Road_Surface_Classification_Dataset) | [dry vs wet](https://github.com/khub-ai/patchbench/tree/main/benchmarks/road_surface/dry_vs_wet) | 0.78 | 0.32 | 0.62 | +0.33 | 1.00 |
| 🟡 partial | `claude-haiku-4-5-20251001` | [road_surface](https://github.com/ztsrxh/RSCD-Road_Surface_Classification_Dataset) | [dry vs wet](https://github.com/khub-ai/patchbench/tree/main/benchmarks/road_surface/dry_vs_wet) | 0.76 | 0.38 | 0.62 | +0.04 | 1.00 |
| 🟡 partial | `qwen/qwen3-vl-8b-instruct` | [dermatology](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T) | [melanoma vs nevus](https://github.com/khub-ai/patchbench/tree/main/benchmarks/dermatology/melanoma_vs_nevus) | 0.75 | 0.44 | 0.67 | -0.12 | 1.00 |
| 🟡 partial | `openai/gpt-4o` | [road_surface](https://github.com/ztsrxh/RSCD-Road_Surface_Classification_Dataset) | [dry vs wet](https://github.com/khub-ai/patchbench/tree/main/benchmarks/road_surface/dry_vs_wet) | 0.72 | 0.26 | 0.54 | +0.08 | 0.60 |
| 🟡 partial | `claude-haiku-4-5-20251001` | [birds](https://www.vision.caltech.edu/datasets/cub_200_2011/) | [bronzed vs shiny cowbird](https://github.com/khub-ai/patchbench/tree/main/benchmarks/birds/bronzed_vs_shiny_cowbird) | 0.67 | 0.21 | 0.62 | +0.17 | 0.60 |
| 🟢 go | `google/gemma-4-26b-a4b-it` | [birds](https://www.vision.caltech.edu/datasets/cub_200_2011/) | [bronzed vs shiny cowbird](https://github.com/khub-ai/patchbench/tree/main/benchmarks/birds/bronzed_vs_shiny_cowbird) | 0.66 | 0.26 | 0.46 | +0.50 | 1.00 |
| 🟡 partial | `google/gemma-4-26b-a4b-it` | [dermatology](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T) | [actinic vs benign keratosis](https://github.com/khub-ai/patchbench/tree/main/benchmarks/dermatology/actinic_vs_benign_keratosis) | 0.62 | 0.24 | 0.67 | +0.04 | 1.00 |
| 🟡 partial | `openai/gpt-4o` | [birds](https://www.vision.caltech.edu/datasets/cub_200_2011/) | [bronzed vs shiny cowbird](https://github.com/khub-ai/patchbench/tree/main/benchmarks/birds/bronzed_vs_shiny_cowbird) | 0.61 | 0.28 | 0.79 | +0.12 | 1.00 |
| 🟢 go | `qwen/qwen3-vl-8b-instruct` | [birds](https://www.vision.caltech.edu/datasets/cub_200_2011/) | [bronzed vs shiny cowbird](https://github.com/khub-ai/patchbench/tree/main/benchmarks/birds/bronzed_vs_shiny_cowbird) | 0.60 | 0.29 | 0.42 | +0.33 | 1.00 |

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
| birds | [CUB-200-2011](https://www.vision.caltech.edu/datasets/cub_200_2011/) | Caltech | Research use |
| dermatology | [HAM10000](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T) | ViDIR Group, Medical University of Vienna | CC BY-NC-SA 4.0 |

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