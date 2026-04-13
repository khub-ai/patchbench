## PR type

<!-- Check one -->
- [ ] Model result submission
- [ ] New benchmark domain
- [ ] Runner / tooling improvement
- [ ] Documentation

---

## Model result submission

<!-- Fill in if this PR adds a result JSON. Delete section otherwise. -->

| Field | Value |
|---|---|
| Model | <!-- e.g. qwen/qwen3-vl-8b-instruct --> |
| Benchmark | <!-- e.g. road_surface_dry_vs_wet_probe_v1 --> |
| Verdict | <!-- go / partial / no-go --> |
| Perception score | <!-- 0.XX or N/A --> |
| Rule delta | <!-- +0.XX --> |
| Consistency | <!-- 0.XX or N/A --> |

**Result file:** `results/<domain>/<pair_id>/<model_tag>.json`

### Checklist

- [ ] Result file is at `results/<domain>/<pair_id>/<model_tag>.json`
- [ ] `validate_result.py` passes locally (`python scripts/validate_result.py <file>`)
- [ ] `pupil_model` exactly matches the model ID used (e.g. `qwen/qwen3-vl-8b-instruct`)
- [ ] `benchmark_id` and `benchmark_version` match the manifest
- [ ] No image files, API keys, or cache files included
- [ ] I ran the probe myself and can reproduce the result

---

## New benchmark domain

<!-- Fill in if this PR adds a new benchmark. Delete section otherwise. -->

**Domain:** <!-- e.g. satellite_imagery -->
**Confusable pair:** <!-- e.g. urban vs forest -->
**Source dataset:** <!-- name, URL, license -->
**Image count:** <!-- e.g. 24 (12 per class) -->

### Patchability pre-screen

| Dimension | Score / assessment |
|---|---|
| G (grounding) | |
| V (vocabulary gap) | |
| B (zero-shot baseline) | |
| E (expert convergence) | |

### Checklist

- [ ] GitHub Issue opened and approved before images collected
- [ ] Source dataset license permits redistribution of small curated subsets
- [ ] Entry added to `DATA_LICENSE.md` with full attribution
- [ ] `precomputed{}` section populated in manifest (or explained why not)
- [ ] Images are ≤ 500 KB total

---

## Runner / tooling improvement

<!-- Brief description of what this changes and why. -->
