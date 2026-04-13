# PatchBench Development Guide

For maintainers and contributors working on the benchmark itself (not just
submitting model results). If you only want to test your own model, see
[getting_started.md](getting_started.md).

---

## Repository relationship

PatchBench is the **public benchmark face** of the DD research system. The
**research engine** lives in a separate repository:

| Repo | Purpose | Visibility |
|---|---|---|
| [khub-ai/patchbench](https://github.com/khub-ai/patchbench) | Stable benchmark, community results, leaderboard | Public, MIT |
| [khub-ai/khub-knowledge-fabric](https://github.com/khub-ai/khub-knowledge-fabric) | DD research system, domain configs, experiment runner | Research, restricted |

The dependency is **one-directional**: KF generates manifests and pre-computed
outputs that get committed here. PatchBench has no runtime dependency on KF.

### What KF provides that PatchBench uses

| KF artifact | Where it ends up in PatchBench |
|---|---|
| `create_benchmark.py` output | `benchmarks/<domain>/<pair>/probe_v1/manifest.json` |
| RSCD probe images (extracted from zip) | `benchmarks/road_surface/.../images/` |
| `probe_rscd.py` output (after `--recompute-tutor`) | `manifest.json` precomputed section |
| DD session accepted rules | can be used as `seed_rule` in manifest |

---

## Benchmark manifest lifecycle

### 1. New domain proposed

Open a GitHub Issue. Include patchability assessment (see
[patchability.md](patchability.md)) for all four dimensions (G, V, B, E).
Maintainer approves before images are collected.

### 2. Images collected (maintainer, requires KF + source dataset)

```bash
# In KF repo:
cd usecases/image-classification/<domain>/python
python create_benchmark.py --pair <pair_id> --types probe --n-probe 12
# Output: usecases/.../benchmarks/<pair_id>_probe_v1.json
```

Copy images manually from source dataset (or use `resolve_path()` in KF):
```bash
# 24 images, ~450KB total
cp /path/to/extracted/images/*.jpg \
   C:/_backup/github/patchbench/benchmarks/<domain>/<pair>/probe_v1/images/
```

### 3. Manifest adapted for PatchBench format

The KF manifest uses flat per-image fields (`friction`, `material`, etc.).
The PatchBench manifest wraps these in `metadata{}`. Adapt with:

```python
# See the conversion script used for road_surface in session history,
# or adapt the pattern: pop domain-specific fields into entry["metadata"]
```

Key additions vs KF manifest:
- `"schema_version": "1.0"`
- `"images_dir": "images/"`
- `"precomputed": { ... }` skeleton (populated in next step)

### 4. Pre-computed outputs generated (maintainer, one-time)

```bash
# In PatchBench repo:
python run_probe.py \
    --pupil-model <any-model> \
    --benchmark benchmarks/<domain>/<pair>/probe_v1/manifest.json \
    --recompute-tutor \
    --tutor-model <your-tutor-model> \
    --validator-model <your-validator-model> \
    --save-precomputed   # writes outputs back into manifest.json (P0 — not yet implemented)
```

The result JSON contains TUTOR descriptions, feature queries, and VALIDATOR
answers. Copy these into the manifest's `precomputed` section:

```python
import json
from pathlib import Path

result = json.loads(Path("results/.../result.json").read_text())
manifest = json.loads(Path("benchmarks/.../manifest.json").read_text())

# These keys come from the probe runner's internal state —
# currently they are NOT in the result JSON (gap to fix).
# Until fixed: run with --recompute-tutor and capture outputs
# from the runner's _get_tutor_descriptions() return values.
```

> **Known gap**: the current runner saves the final ProbeResult but does not
> separately save the intermediate TUTOR/VALIDATOR outputs needed to populate
> `precomputed{}`. This needs to be added to `runner/probe.py` —
> `run_probe()` should return or save the precomputed dict alongside the result.
> Track as GitHub Issue.

### 5. Commit and push

```bash
git add benchmarks/<domain>/
git commit -m "Add <domain> <pair> probe_v1 benchmark with precomputed outputs"
git push
```

---

## Adding a result (CI validation)

Currently there is no CI. Result PRs are validated manually. Planned CI:

```yaml
# .github/workflows/validate_result.yml  (not yet implemented)
# - validate result JSON against ProbeResult schema
# - check benchmark_id matches an existing manifest
# - check pupil_model field is non-empty
# - regenerate leaderboard.md and commit to PR
```

Track as GitHub Issue.

---

## Regenerating the leaderboard

After merging result PRs:

```bash
python leaderboard/generate.py
git add leaderboard/leaderboard.md
git commit -m "Regenerate leaderboard"
git push
```

The `leaderboard.json` file is gitignored (machine-readable, rebuilt each time).
The `leaderboard.md` file is committed (human-readable, rendered on GitHub).

---

## Known gaps and roadmap

These are the things a new session should tackle first, in priority order:

### P0 — Must fix before benchmark is usable

**1. Add `--save-precomputed` flag to runner**
`run_probe.py --recompute-tutor --save-precomputed manifest.json` should
write the TUTOR/VALIDATOR outputs back into the manifest file automatically.
Currently there is no automated path to populate `precomputed{}` — the runner
saves the final ProbeResult but not the intermediate TUTOR/VALIDATOR outputs
needed to fill the manifest. This is a runner feature, not domain-specific.

**2. Populate `precomputed{}` in all committed manifests**
Once `--save-precomputed` is implemented, run it for each benchmark manifest
and commit the result. Until this is done for a given benchmark, contributors
running that benchmark must supply credentials for both TUTOR and VALIDATOR
models in addition to their PUPIL model.

### P1 — Important for usability

**3. CI schema validation for result PRs**
`validate_result.yml` GitHub Action that checks result JSON schema before merge.

**4. Add first official result**
Run Qwen3-VL-8B on road_surface dry_vs_wet and commit the result. This proves
the pipeline works end-to-end and seeds the leaderboard.

**5. Dermatology and birds benchmarks**
Both have confirmed DD results in KF (50%→100% pilot on melanoma/nevus,
33%→83% on Bronzed/Shiny Cowbird). Images available from HAM10000 and
CUB-200-2011. These are the two strongest patchability demonstrations —
critical for benchmark credibility.

### P2 — Nice to have

**6. Static leaderboard HTML**
Generate a styled `leaderboard/index.html` from `leaderboard.json` for
embedding or GitHub Pages hosting.

**7. Multi-benchmark runner**
`python run_probe.py --all-benchmarks --pupil-model your/model` to run all
available benchmarks in one command and produce a cross-domain profile.

**8. Temperature standardisation**
Document recommended temperature settings per model family. Consistency scores
are not comparable across temperature settings.

---

## Schema stability contract

- `schema_version` in manifest and result JSONs follows semver
- Minor version bumps (new optional fields) are backwards compatible
- Major version bumps require a migration note in this document
- Current version: **1.0**

Fields marked as required in `runner/schema.py` dataclasses must not be removed
or renamed without a major version bump.

---

## Source dataset licenses and compliance

All benchmark images must comply with their source dataset's license.
See [DATA_LICENSE.md](../DATA_LICENSE.md) for current per-domain attribution.

Before adding images from a new dataset:
1. Confirm the license permits inclusion of small curated subsets in a public repo
2. Add an entry to `DATA_LICENSE.md` with full attribution and download URL
3. Add the dataset to the sources table in `docs/getting_started.md`

Licenses that permit inclusion: CC BY, CC BY-SA, CC BY-NC, CC BY-NC-SA,
research-use with attribution. When in doubt, email the dataset authors.

---

## Contact and research context

PatchBench is built on Dialogic Distillation research. For the full technical
background:

- **Research paper**: in preparation
- **Research codebase**: [khub-ai/khub-knowledge-fabric](https://github.com/khub-ai/khub-knowledge-fabric)
- **Theory**: [patchability.md](patchability.md) and [probe_design.md](probe_design.md)
- **Issues and PRs**: https://github.com/khub-ai/patchbench/issues
