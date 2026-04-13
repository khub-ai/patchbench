"""
run_probe.py — PatchBench command-line entry point.

Tests whether your VLM can be patched with expert rules for a given domain.

Quick start:
  pip install -r runner/requirements.txt
  export ANTHROPIC_API_KEY=sk-ant-...
  export OPENROUTER_API_KEY=sk-or-...
  python run_probe.py --pupil-model qwen/qwen3-vl-8b-instruct

More options:
  python run_probe.py --list-benchmarks
  python run_probe.py --pupil-model your/model --benchmark benchmarks/road_surface/dry_vs_wet/probe_v1/manifest.json
  python run_probe.py --pupil-model your/model --recompute-tutor --tutor-model claude-opus-4-6
  python run_probe.py --clear-cache

Submit your result:
  git add results/...
  git commit -m "Add probe result: your-model on road_surface dry_vs_wet"
  gh pr create
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from runner.probe import run_probe, clear_cache
from runner.schema import VERDICT_GO, VERDICT_PARTIAL, VERDICT_NO_GO

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()
    _RICH = True
except ImportError:
    console = None
    _RICH = False


DEFAULT_BENCHMARK = "benchmarks/road_surface/dry_vs_wet/probe_v1/manifest.json"
DEFAULT_TUTOR     = "claude-opus-4-6"
DEFAULT_VALIDATOR = "claude-sonnet-4-6"
RESULTS_DIR       = _HERE / "results"
CACHE_DIR         = _HERE / ".cache" / "probe"


def _list_benchmarks():
    manifests = sorted(_HERE.glob("benchmarks/**/manifest.json"))
    if not manifests:
        print("No benchmark manifests found under benchmarks/")
        return
    print(f"\n{'Benchmark':<55} {'Domain':<15} {'Pair':<20} {'Images'}")
    print("-" * 100)
    import json
    for p in manifests:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            rel = str(p.relative_to(_HERE))
            print(f"{d.get('benchmark_id','?'):<55} "
                  f"{d.get('domain','?'):<15} "
                  f"{d.get('pair_id','?'):<20} "
                  f"{len(d.get('images',[]))}")
        except Exception:
            pass


def parse_args():
    p = argparse.ArgumentParser(
        description="PatchBench — test whether your VLM can be patched with expert rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_probe.py --pupil-model qwen/qwen3-vl-8b-instruct
  python run_probe.py --pupil-model llava-hf/llava-1.5-7b-hf
  python run_probe.py --list-benchmarks
  python run_probe.py --clear-cache
        """,
    )
    p.add_argument("--pupil-model",    default="",
                   help="Model to test (OpenRouter or Anthropic model ID)")
    p.add_argument("--benchmark",      default=DEFAULT_BENCHMARK,
                   help=f"Path to manifest.json  [default: {DEFAULT_BENCHMARK}]")
    p.add_argument("--tutor-model",    default=DEFAULT_TUTOR,
                   help=f"TUTOR model  [default: {DEFAULT_TUTOR}]")
    p.add_argument("--validator-model", default=DEFAULT_VALIDATOR,
                   help=f"VALIDATOR model  [default: {DEFAULT_VALIDATOR}]")
    p.add_argument("--recompute-tutor", action="store_true",
                   help="Regenerate TUTOR/VALIDATOR outputs instead of using pre-committed values")
    p.add_argument("--output",         default="",
                   help="Output path for result JSON (default: auto under results/)")
    p.add_argument("--list-benchmarks", action="store_true")
    p.add_argument("--clear-cache",    action="store_true",
                   help="Clear TUTOR/VALIDATOR disk cache")
    p.add_argument("--anthropic-key",  default="",
                   help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    p.add_argument("--openrouter-key", default="",
                   help="OpenRouter API key (or set OPENROUTER_API_KEY env var)")
    return p.parse_args()


async def main():
    args = parse_args()

    if args.list_benchmarks:
        _list_benchmarks()
        return

    if args.clear_cache:
        clear_cache(disk=True, cache_dir=CACHE_DIR)
        print("Cache cleared.")
        return

    if not args.pupil_model:
        print("Error: --pupil-model is required.")
        print("Example: python run_probe.py --pupil-model qwen/qwen3-vl-8b-instruct")
        sys.exit(1)

    anthropic_key  = args.anthropic_key  or os.environ.get("ANTHROPIC_API_KEY", "")
    openrouter_key = args.openrouter_key or os.environ.get("OPENROUTER_API_KEY", "")

    if not anthropic_key and not args.recompute_tutor:
        # Pre-committed outputs don't need Anthropic key — but validator scoring does
        pass  # will error naturally if needed

    benchmark_path = Path(args.benchmark)
    if not benchmark_path.is_absolute():
        benchmark_path = _HERE / benchmark_path
    if not benchmark_path.exists():
        print(f"Benchmark not found: {benchmark_path}")
        print("Run: python run_probe.py --list-benchmarks")
        sys.exit(1)

    result = await run_probe(
        manifest_path   = benchmark_path,
        pupil_model     = args.pupil_model,
        tutor_model     = args.tutor_model,
        validator_model = args.validator_model,
        recompute_tutor = args.recompute_tutor,
        anthropic_key   = anthropic_key,
        openrouter_key  = openrouter_key,
        cache_dir       = CACHE_DIR,
        console         = console,
    )

    # Save result
    model_tag  = args.pupil_model.replace("/", "_").replace("-", "_").replace(".", "_")
    import json
    manifest_data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    domain   = manifest_data.get("domain", "unknown")
    pair_id  = manifest_data.get("pair_id", "unknown")

    out_path = Path(args.output) if args.output else (
        RESULTS_DIR / domain / pair_id / f"{model_tag}.json"
    )
    result.save(out_path)
    print(f"\nResult saved: {out_path}")
    print(f"To submit: git add {out_path.relative_to(_HERE)} && git commit -m "
          f"'Add probe: {args.pupil_model} on {domain} {pair_id}'")

    # Final banner
    colour = {"go": "✅", "partial": "⚠️", "no-go": "❌"}[result.verdict]
    print(f"\n{colour}  Verdict: {result.verdict.upper()}")
    print(f"   Perception:   {result.perception_score:.2f}")
    print(f"   Rule delta:   {result.rule_comprehension_delta:+.2f}")
    print(f"   Consistency:  {result.consistency_score:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
