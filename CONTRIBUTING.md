# Contributing to PatchBench

Three ways to contribute:

1. **[Submit a model result](#1-submit-a-model-result)** — run the probe on your model, open a PR
2. **[Add a new domain](#2-add-a-new-domain)** — propose a new image domain with patchability evidence
3. **[Improve the runner](#3-improve-the-runner)** — bug fixes, new model backends, CI improvements

---

## 1. Submit a model result

### Prerequisites

- Python 3.10+
- `OPENROUTER_API_KEY` (for your PUPIL model) **or** your own API endpoint
- `ANTHROPIC_API_KEY` (for VALIDATOR scoring — only needed if pre-computed outputs are missing)

### Steps

**1. Clone and install**

```bash
git clone https://github.com/khub-ai/patchbench
cd patchbench
pip install -r runner/requirements.txt
```

**2. Run the probe**

```bash
export OPENROUTER_API_KEY=sk-or-...
export ANTHROPIC_API_KEY=sk-ant-...   # only needed for validator scoring

python run_probe.py --pupil-model your-org/your-model-name
```

List available benchmarks:
```bash
python run_probe.py --list-benchmarks
```

Run against a specific benchmark:
```bash
python run_probe.py \
    --pupil-model your-org/your-model \
    --benchmark benchmarks/road_surface/dry_vs_wet/probe_v1/manifest.json
```

**3. Verify your result file**

The result is saved to `results/<domain>/<pair_id>/<model_tag>.json`.
Check it looks reasonable:

```bash
cat results/road_surface/dry_vs_wet/your_model_tag.json | python -m json.tool | head -30
```

The result must include:
- `verdict`: `"go"` / `"partial"` / `"no-go"`
- `benchmark_id` matching the manifest
- `submitted` timestamp
- `pupil_model` matching what you ran

**4. Open a PR**

```bash
git checkout -b result/road-surface-your-model
git add results/road_surface/dry_vs_wet/your_model_tag.json
git commit -m "Add probe result: your-model on road_surface dry_vs_wet"
gh pr create --title "Result: your-model on road_surface dry_vs_wet" \
    --body "Verdict: go/partial/no-go. Perception: 0.XX. Notes: ..."
```

### PR checklist

- [ ] Result JSON validates against the schema (CI checks this automatically)
- [ ] `pupil_model` field exactly matches the model ID used
- [ ] `benchmark_id` and `benchmark_version` match the manifest
- [ ] No image files or API keys included in the commit
- [ ] PR title follows format: `Result: <model> on <domain> <pair>`

### Cost estimate

| PUPIL model | Estimated cost | API |
|---|---|---|
| Qwen3-VL-8B (OpenRouter) | ~$0.01 | OpenRouter |
| LLaVA-1.5-7B (OpenRouter) | ~$0.01 | OpenRouter |
| GPT-4o (OpenAI) | ~$0.30 | OpenAI |
| Claude Sonnet (Anthropic) | ~$0.15 | Anthropic |

VALIDATOR calls (Sonnet) add ~$0.03. TUTOR calls are pre-committed and free.

---

## 2. Add a new domain

New domains must pass the **patchability pre-screen** before images are
collected and manifests committed. This prevents investing effort in domains
where DD structurally cannot work.

### Step 1: Patchability pre-screen

Read [docs/patchability.md](docs/patchability.md) and assess your domain
across the four dimensions:

| Dimension | Threshold for proceeding |
|---|---|
| G (grounding) | Expert features visually observable > 0.40 |
| V (vocabulary gap) | Expert uses domain-specific terms PUPIL doesn't |
| B (zero-shot baseline) | 0.40–0.75 (genuine confusion, not saturated) |
| E (expert convergence) | Domain expert articulates clear distinctions |

Open a GitHub Issue with your assessment before spending time on images.

### Step 2: Identify source dataset

Requirements:
- Publicly available (Kaggle, Zenodo, HuggingFace, or direct download)
- Clear license that permits inclusion of small curated subsets for research
- Sufficient labeled images for the target confusable pair (≥ 500 per class)
- Ground truth labels that are unambiguous (not subjective or crowd-sourced)

Acceptable licenses for image inclusion: CC BY, CC BY-SA, CC BY-NC,
CC BY-NC-SA, research-use licenses with attribution.

Not acceptable: licenses prohibiting redistribution, proprietary datasets
without explicit research permission.

### Step 3: Collect 24 probe images (12 per class)

Images should:
- Cover the full difficulty range (easy / medium / hard)
- Be representative of real deployment conditions
- Not include images that are trivially distinguishable (e.g. different lighting conditions, not content)

For difficulty annotation without TUTOR API calls, assign structurally:
- easy: unambiguous examples
- medium: typical examples
- hard: borderline examples a human might pause on

### Step 4: Create the manifest

```python
# See benchmarks/road_surface/dry_vs_wet/probe_v1/manifest.json for format
# Required fields: benchmark_id, schema_version, version, domain, pair_id,
#                  class_a, class_b, description, images[]
# Optional but recommended: precomputed{} with TUTOR/VALIDATOR outputs
```

### Step 5: Open a PR

```bash
git add benchmarks/<domain>/<pair>/probe_v1/
git commit -m "Add benchmark: <domain> <pair> probe_v1"
```

Include in your PR description:
- Patchability assessment (all four dimensions)
- Source dataset citation and license
- How images were selected and difficulty assigned

---

## 3. Improve the runner

Standard open-source workflow: fork → branch → PR.

Areas where contributions are especially welcome:

- **New model backends**: local vLLM, HuggingFace Inference API, Replicate
- **CI validation**: GitHub Actions schema validation for result PRs
- **Leaderboard UI**: static HTML leaderboard from `leaderboard.json`
- **Multi-domain runs**: run probe across all available benchmarks in one call
- **Result comparison**: diff two result files, flag regressions

Code style: no linter enforced, but match the existing style (type hints,
async throughout, no global state beyond the cache dict).

---

## Code of conduct

Be direct and precise. Benchmark submissions are judged on reproducibility,
not on how well a model scores. A reproducible `no-go` result is as valuable
as a `go` — it tells the community which models to avoid investing in for DD.

Do not submit results you cannot reproduce. The per-image breakdown in every
result JSON is designed to make spot-checking straightforward.
