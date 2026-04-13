"""
validate_result.py — Validate a PatchBench ProbeResult JSON before submission.

Usage:
    python scripts/validate_result.py results/road_surface/dry_vs_wet/my_model.json
    python scripts/validate_result.py results/**/*.json   # glob, via shell expansion

Exit codes:
    0 — all files passed
    1 — one or more files failed validation

Also used by CI (.github/workflows/validate_result.yml).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FIELDS = [
    "benchmark_id", "benchmark_version", "schema_version", "submitted",
    "pupil_model", "tutor_model", "validator_model", "verdict",
    "zero_shot_accuracy", "rule_aided_accuracy", "rule_comprehension_delta",
    "weak_points", "recommendations", "costs", "total_cost_usd",
]
VALID_VERDICTS   = {"go", "partial", "no-go"}
VALID_SCHEMAS    = {"1.0"}
SCORE_FIELDS     = [
    "perception_score", "vocabulary_overlap",
    "zero_shot_accuracy", "rule_aided_accuracy", "consistency_score",
]


def _err(path: Path, msg: str) -> str:
    return f"  FAIL  {path.relative_to(_ROOT)}  —  {msg}"


def validate(path: Path) -> list[str]:
    """Return a list of error strings (empty = valid)."""
    errors = []

    # ------------------------------------------------------------------ load
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [_err(path, f"JSON parse error: {e}")]

    if not isinstance(data, dict):
        return [_err(path, "root must be a JSON object")]

    # --------------------------------------------------------- required fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(_err(path, f"missing required field: {field}"))

    if errors:
        return errors  # no point continuing if fields are absent

    # ------------------------------------------------------------ field values
    if data.get("verdict") not in VALID_VERDICTS:
        errors.append(_err(path, f"verdict must be one of {VALID_VERDICTS}, "
                                  f"got {data.get('verdict')!r}"))

    if data.get("schema_version") not in VALID_SCHEMAS:
        errors.append(_err(path, f"schema_version must be one of {VALID_SCHEMAS}, "
                                  f"got {data.get('schema_version')!r}"))

    if not data.get("pupil_model", "").strip():
        errors.append(_err(path, "pupil_model must be non-empty"))

    if not data.get("benchmark_id", "").strip():
        errors.append(_err(path, "benchmark_id must be non-empty"))

    # ----------------------------------------------------- numeric range check
    for field in SCORE_FIELDS:
        v = data.get(field)
        if v is None:
            continue   # Optional — None is allowed (pre-manifest DD session imports)
        if not isinstance(v, (int, float)):
            errors.append(_err(path, f"{field} must be a number, got {type(v).__name__}"))
        elif not (0.0 <= v <= 1.0):
            errors.append(_err(path, f"{field} out of range [0, 1]: {v}"))

    delta = data.get("rule_comprehension_delta")
    if delta is not None and not isinstance(delta, (int, float)):
        errors.append(_err(path, "rule_comprehension_delta must be a number"))

    # ------------------------------------------- benchmark_id vs manifest check
    benchmark_id = data.get("benchmark_id", "")
    if benchmark_id and not benchmark_id.endswith("_dd_session_v0"):
        # For formal benchmark results, check that a matching manifest exists.
        # Naming convention: benchmark_id = <domain>_<pair_id>_probe_v<N>
        # Manifest lives at: benchmarks/<domain>/<pair_id>/probe_v<N>/manifest.json
        parts = benchmark_id.rsplit("_probe_v", 1)
        if len(parts) == 2:
            prefix, version = parts
            # prefix is like "road_surface_dry_vs_wet"
            # Try to find domain/pair_id split by looking for matching dirs
            found = list((_ROOT / "benchmarks").glob(f"**/probe_v{version}/manifest.json"))
            matching = [
                p for p in found
                if p.parent.parent.parent.name + "_" + p.parent.parent.name + "_probe_v" + version
                   == benchmark_id
            ]
            if not matching:
                errors.append(_err(path, f"no manifest found for benchmark_id {benchmark_id!r}. "
                                          f"Expected benchmarks/<domain>/<pair_id>/probe_v{version}/"
                                          f"manifest.json to exist."))

    # ------------------------------------------- path convention check
    # results/<domain>/<pair_id>/<model_tag>.json
    rel = path.relative_to(_ROOT)
    parts = rel.parts
    if len(parts) != 4 or parts[0] != "results":
        errors.append(_err(path, f"file must be at results/<domain>/<pair_id>/<model_tag>.json, "
                                  f"got {rel}"))

    return errors


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: python scripts/validate_result.py <result.json> [...]")
        return 1

    paths = [Path(a).resolve() for a in argv]
    all_errors: list[str] = []
    checked = 0

    for p in paths:
        if not p.exists():
            all_errors.append(f"  FAIL  {p}  —  file not found")
            continue
        errs = validate(p)
        checked += 1
        if errs:
            all_errors.extend(errs)
        else:
            rel = p.relative_to(_ROOT) if p.is_relative_to(_ROOT) else p
            print(f"  OK    {rel}")

    if all_errors:
        print()
        for e in all_errors:
            print(e)
        print(f"\n{len(all_errors)} error(s) in {checked} file(s).")
        return 1

    print(f"\nAll {checked} file(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
