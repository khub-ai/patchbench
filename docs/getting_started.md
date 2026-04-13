# Getting Started with PatchBench

## What you need

| Item | Purpose |
|---|---|
| Python 3.10+ | Running the probe |
| API key(s) for the models you plan to use | PUPIL, TUTOR, and VALIDATOR calls |

PatchBench uses three model roles:

| Role | When called | Default model |
|---|---|---|
| **PUPIL** | Every run — this is the model under test | *(you choose)* |
| **TUTOR** | Only with `--recompute-tutor`; otherwise served from pre-committed manifest | `claude-opus-4-6` |
| **VALIDATOR** | Step 2 (vocabulary overlap) every run; Steps 1+3 only with `--recompute-tutor` | `claude-sonnet-4-6` |

The defaults (`claude-opus-4-6` / `claude-sonnet-4-6`) are Anthropic models and
require `ANTHROPIC_API_KEY`. Any model can be substituted via `--tutor-model`
and `--validator-model` — including local models served on an OpenAI-compatible
endpoint. See [Custom model backends](#custom-model-backends) for details.

The runner picks up API keys from environment variables:
- `ANTHROPIC_API_KEY` — for Anthropic models
- `OPENROUTER_API_KEY` — for models accessed via [OpenRouter](https://openrouter.ai)

Or pass them explicitly with `--anthropic-key` / `--openrouter-key`.

---

## Installation

```bash
git clone https://github.com/khub-ai/patchbench
cd patchbench
pip install -r runner/requirements.txt
```

No dataset download needed. The benchmark images are already in
`benchmarks/road_surface/dry_vs_wet/probe_v1/images/` (24 JPEGs, 450 KB total).

---

## Run your first probe

```bash
# Set keys for whichever model providers you are using
export ANTHROPIC_API_KEY=...      # needed for default VALIDATOR (claude-sonnet-4-6)
export OPENROUTER_API_KEY=...     # needed if your PUPIL is on OpenRouter

python run_probe.py --pupil-model your-org/your-model
```

Expected output:

```
PatchBench Probe
  PUPIL:     qwen/qwen3-vl-8b-instruct
  Benchmark: road_surface_dry_vs_wet_probe_v1  (24 images)
  Pair:      Dry Road vs Wet Road

  Using pre-committed TUTOR/VALIDATOR outputs (claude-opus-4-6, claude-sonnet-4-6)

  Step 1/4  Expert descriptions + feature queries...
    24 descriptions, 12 feature queries
  Step 2/4  PUPIL vocabulary probe...
    Vocabulary overlap: 0.31
  Step 3/4  Feature detection probe...
    Easy: 0.72  Medium: 0.55  Hard: 0.38  Overall: 0.55
  Step 4/4  Rule comprehension + consistency...
    Zero-shot: 0.46  Rule-aided: 0.63  Delta: +0.17  Consistency: 0.80

  Verdict: PARTIAL

Result saved: results/road_surface/dry_vs_wet/qwen_qwen3_vl_8b_instruct.json
```

---

## What the scores mean

**Perception score** (Step 3 overall) — fraction of feature detection queries
the PUPIL answers correctly (judged against VALIDATOR ground truth). Measures
whether PUPIL can see what expert rules will refer to.

**Rule comprehension delta** (Step 4) — accuracy gain from injecting a rule.
Positive = PUPIL follows expert instructions. Near-zero = rules are ignored.

**Consistency** (Step 4) — fraction of images where repeating the same prompt
gives the same answer. Low consistency means even perfect rules won't help.

---

## Available benchmarks

```bash
python run_probe.py --list-benchmarks
```

---

## Choosing your VALIDATOR model

When TUTOR/VALIDATOR outputs are already pre-committed in the manifest, the
VALIDATOR is only used for Step 2 (vocabulary overlap scoring). You can
substitute any model you have access to:

```bash
python run_probe.py \
    --pupil-model your/model \
    --validator-model your-preferred-validator
```

Note: scores are not directly comparable across different VALIDATOR models.
Official leaderboard results use the VALIDATOR recorded in the manifest's
`precomputed.validator_model` field.

---

## Regenerating TUTOR outputs

If you want to verify or regenerate the pre-committed TUTOR/VALIDATOR outputs
from scratch, use `--recompute-tutor` and specify your preferred models:

```bash
python run_probe.py \
    --pupil-model your/model \
    --recompute-tutor \
    --tutor-model your-preferred-tutor \
    --validator-model your-preferred-validator
```

This is useful for auditing the pre-committed outputs or experimenting with
a different TUTOR model. Results will differ from the official leaderboard
if different TUTOR/VALIDATOR models are used.

---

## Custom model backends

The runner uses OpenAI-compatible API format for non-Claude models. Any server
that speaks this protocol works:

```bash
# Local vLLM server
python run_probe.py \
    --pupil-model Qwen/Qwen2-VL-7B-Instruct \
    --openrouter-key dummy \
    OPENAI_BASE_URL=http://localhost:8000/v1 \
    python run_probe.py ...
```

Or edit `runner/models.py` to add a custom backend.

---

## Submitting your result

See [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Source datasets

The benchmark images are curated subsets from:

| Domain | Dataset | Source | License |
|---|---|---|---|
| Road surface | [RSCD](https://github.com/ztsrxh/RSCD-Road_Surface_Classification_Dataset) | Tsinghua University | CC BY-NC-SA 4.0 |
| Dermatology (planned) | [HAM10000](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T) | ViDIR Group, Medical University of Vienna | CC BY-NC-SA 4.0 |
| Birds (planned) | [CUB-200-2011](https://www.vision.caltech.edu/datasets/cub_200_2011/) | Caltech | Research use |

For full license text and attribution requirements, see
[DATA_LICENSE.md](../DATA_LICENSE.md).

---

## Related work

- [KHub Knowledge Fabric](https://github.com/khub-ai/khub-knowledge-fabric) —
  the DD research system that PatchBench benchmarks against
- [Dialogic Distillation paper](#) — coming soon
- [Patchability theory](patchability.md) — when does DD work and why?
