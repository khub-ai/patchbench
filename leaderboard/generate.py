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
from datetime import datetime, timezone
from pathlib import Path

_HERE    = Path(__file__).resolve().parent
_ROOT    = _HERE.parent
_RESULTS = _ROOT / "results"

VERDICT_COLOUR = {"go": "🟢", "partial": "🟡", "no-go": "🔴"}

# KF usecase subdirectory per domain — used as fallback pair link when
# no PatchBench benchmark manifest exists yet for that pair.
_KF_BASE = "https://github.com/khub-ai/khub-knowledge-fabric/tree/main"
KF_USECASE_PATH = {
    "road_surface": f"{_KF_BASE}/usecases/image-classification/road-surface",
    "birds":        f"{_KF_BASE}/usecases/image-classification/birds",
    "dermatology":  f"{_KF_BASE}/usecases/image-classification/dermatology",
}

_PB_BASE = "https://github.com/khub-ai/patchbench/tree/main"


def _pair_url(domain: str, pair_id: str) -> str:
    """Return the best available URL for a (domain, pair_id) combination.

    Priority:
    1. PatchBench benchmark directory — if benchmarks/<domain>/<pair_id>/ exists
       (committed manifest + images → stable public reference).
    2. KF usecase directory — for pre-manifest DD session results where only
       the research repo holds the experiment artefacts.
    3. Empty string — no link available.
    """
    pb_dir = _ROOT / "benchmarks" / domain / pair_id
    if pb_dir.is_dir():
        return f"{_PB_BASE}/benchmarks/{domain}/{pair_id}"
    return KF_USECASE_PATH.get(domain, "")


# Source dataset links per domain — shown in the leaderboard table and data sources section.
DOMAIN_DATASET = {
    "road_surface": {
        "name":    "RSCD",
        "url":     "https://github.com/ztsrxh/RSCD-Road_Surface_Classification_Dataset",
        "credit":  "Tsinghua University",
        "license": "CC BY-NC-SA 4.0",
    },
    "birds": {
        "name":    "CUB-200-2011",
        "url":     "https://www.vision.caltech.edu/datasets/cub_200_2011/",
        "credit":  "Caltech",
        "license": "Research use",
    },
    "dermatology": {
        "name":    "HAM10000",
        "url":     "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DBW86T",
        "credit":  "ViDIR Group, Medical University of Vienna",
        "license": "CC BY-NC-SA 4.0",
    },
}


def _fmt(value, fmt=".2f") -> str:
    """Format a score or return 'N/A' if None."""
    if value is None:
        return "N/A"
    return format(value, fmt)


def _sort_key(r: dict):
    """Sort: measured perception descending, then unmeasured, then model name."""
    p = r["perception"]
    return (0 if p is None else -p, r["model"])


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
                "perception":         data.get("perception_score"),
                "vocab_overlap":      data.get("vocabulary_overlap"),
                "zero_shot":          data["zero_shot_accuracy"],
                "rule_aided":         data["rule_aided_accuracy"],
                "rule_delta":         data["rule_comprehension_delta"],
                "consistency":        data.get("consistency_score"),
                "total_cost_usd":     data["total_cost_usd"],
                "submitted":          data["submitted"],
                "result_file":        str(json_path.relative_to(_ROOT)),
                "notes":              data.get("notes", ""),
            })
        except Exception as e:
            print(f"  Warning: could not parse {json_path}: {e}")
    return sorted(rows, key=_sort_key)


def write_json(rows: list) -> None:
    out = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
        f"> Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')} · "
        f"{len(rows)} result(s)",
        "",
        "Sorted by perception score descending. "
        "See [CONTRIBUTING.md](../CONTRIBUTING.md) to submit your model's results.",
        "",
        "| Verdict | Model | Domain | Confusable pair | Percep. | VocabΔ | ZeroShot | RuleDelta | Consist. |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        v    = VERDICT_COLOUR.get(r["verdict"], r["verdict"])
        pair_label = r["pair_id"].replace("_", " ")
        note = " ⚠" if r.get("notes") else ""

        # Domain cell: links to source dataset
        ds = DOMAIN_DATASET.get(r["domain"])
        domain_cell = f"[{r['domain']}]({ds['url']})" if ds else r["domain"]

        # Pair cell: links to PatchBench benchmark dir if committed, else KF usecase
        pair_url = _pair_url(r["domain"], r["pair_id"])
        pair_cell = f"[{pair_label}]({pair_url})" if pair_url else pair_label

        lines.append(
            f"| {v} {r['verdict']}{note} "
            f"| `{r['model']}` "
            f"| {domain_cell} "
            f"| {pair_cell} "
            f"| {_fmt(r['perception'])} "
            f"| {_fmt(r['vocab_overlap'])} "
            f"| {r['zero_shot']:.2f} "
            f"| {r['rule_delta']:+.2f} "
            f"| {_fmt(r['consistency'])} |"
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
        "",
        "> ⚠ Results with N/A scores were derived from pre-manifest DD session data "
        "(Steps 2 and 3 not run). "
        "RuleDelta and ZeroShot are from expanded validation runs; "
        "Percep, VocabΔ, and Consist were not measured. "
        "These results demonstrate DD effectiveness but cannot produce a full patchability verdict.",
        "",
        "---",
        "",
        "## How to use this leaderboard",
        "",
        "This leaderboard helps you decide whether Dialogic Distillation (DD) is worth "
        "attempting for your domain and PUPIL model, before committing to the full process.",
        "",
        "### Quick path — use an existing benchmark as a proxy",
        "",
        "1. **Find the closest domain.** Browse the table for a confusable pair that resembles "
        "your visual classification task — same image modality, similar level of visual subtlety, "
        "or the same application area (e.g. another dermatology pair as a proxy for your skin-lesion task).",
        "2. **Find your model (or the nearest equivalent).** If your PUPIL model appears in the table, "
        "read its row directly. If not, look for a model of similar size and architecture family.",
        "3. **Read the verdict.**",
        "   - 🟢 **go** — DD is likely to work. The model perceives domain features, follows injected "
        "rules, and gives stable answers. Proceed with building a rule library.",
        "   - 🟡 **partial** — DD may work but will need care. Check which score fell short: "
        "low RuleDelta suggests simpler, shorter rule phrasing; low Consistency suggests "
        "using temperature=0 or majority-vote inference.",
        "   - 🔴 **no-go** — the model lacks the visual grounding needed for this domain. "
        "Consider a larger model, a domain-adapted backbone, or a different PUPIL candidate.",
        "4. **Check RuleDelta specifically.** A high Percep but low RuleDelta means the model "
        "sees the features but does not act on rules — prompt engineering alone is unlikely to fix this. "
        "A low Percep means the model is blind to the discriminating features; rules cannot compensate.",
        "",
        "### Thorough path — run the probe on your own image set",
        "",
        "Use this when no existing benchmark is close enough to your domain, "
        "or when you need a defensible result for your specific model and data.",
        "",
        "1. **Prepare 24 images** — 12 per class, covering the confusable pair you care about. "
        "Include diversity in lighting, angle, and difficulty. "
        "See [CONTRIBUTING.md](../CONTRIBUTING.md) for the manifest format.",
        "2. **Run the probe** against your PUPIL model:",
        "   ```",
        "   python run_probe.py --pupil-model your-org/your-model \\",
        "       --benchmark benchmarks/your_domain/your_pair/probe_v1/manifest.json",
        "   ```",
        "3. **Interpret the result** using the same verdict logic above. "
        "Additionally inspect the per-image breakdowns: "
        "consistent misclassifications on one class point to vocabulary gaps (low VocabΔ); "
        "inconsistent predictions on the same image point to stability problems (low Consist.).",
        "4. **If verdict is go or partial**, proceed to build your rule library using the DD workflow "
        "in [khub-ai/khub-knowledge-fabric](https://github.com/khub-ai/khub-knowledge-fabric). "
        "Start with the failure cases the probe identified — those are the highest-value targets "
        "for expert rule authoring.",
        "5. **Submit your result** via pull request so others with the same model can benefit.",
        "",
        "---",
        "",
        "## Image data sources",
        "",
        "Benchmark images are curated subsets from publicly available datasets.",
        "See [DATA_LICENSE.md](../DATA_LICENSE.md) for full attribution and license text.",
        "",
        "| Domain | Dataset | Credit | License |",
        "|---|---|---|---|",
    ]

    # Emit one row per domain in DOMAIN_DATASET.
    # Mark as "images pending" only when the benchmarks/<domain>/ directory does not exist.
    benchmarks_dir = _ROOT / "benchmarks"
    for domain, ds in DOMAIN_DATASET.items():
        has_images = (benchmarks_dir / domain).is_dir()
        marker = "" if has_images else " *(images pending)*"
        lines.append(
            f"| {domain}{marker} "
            f"| [{ds['name']}]({ds['url']}) "
            f"| {ds['credit']} "
            f"| {ds['license']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Research context",
        "",
        "PatchBench measures **Dialogic Distillation (DD)** patchability — "
        "whether a small VLM can be improved by injecting expert-authored visual "
        "rules at inference time, without any retraining.",
        "",
        "| Resource | Link |",
        "|---|---|",
        "| Benchmark repo | [khub-ai/patchbench](https://github.com/khub-ai/patchbench) |",
        "| DD research system | [khub-ai/khub-knowledge-fabric](https://github.com/khub-ai/khub-knowledge-fabric) |",
        "| Probe design | [docs/probe_design.md](../docs/probe_design.md) |",
        "| Patchability theory | [docs/patchability.md](../docs/patchability.md) |",
        "| How to contribute | [CONTRIBUTING.md](../CONTRIBUTING.md) |",
    ]

    path = _HERE / "leaderboard.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Written: {path.name}")


def write_html(rows: list) -> None:
    """Write leaderboard.html — a self-contained filterable HTML leaderboard."""

    VERDICT_HTML = {"go": "🟢", "partial": "🟡", "no-go": "🔴"}

    def row_html(r: dict) -> str:
        v         = VERDICT_HTML.get(r["verdict"], r["verdict"])
        pair_label = r["pair_id"].replace("_", " ")
        pair_url  = _pair_url(r["domain"], r["pair_id"])
        pair_cell = f'<a href="{pair_url}">{pair_label}</a>' if pair_url else pair_label
        ds        = DOMAIN_DATASET.get(r["domain"])
        dom_cell  = f'<a href="{ds["url"]}">{r["domain"]}</a>' if ds else r["domain"]
        note      = " ⚠" if r.get("notes") else ""
        delta_cls = "positive" if r["rule_delta"] > 0 else ("negative" if r["rule_delta"] < 0 else "")
        return (
            f'<tr>'
            f'<td>{v} {r["verdict"]}{note}</td>'
            f'<td><code>{r["model"]}</code></td>'
            f'<td>{dom_cell}</td>'
            f'<td>{pair_cell}</td>'
            f'<td>{_fmt(r["perception"])}</td>'
            f'<td>{_fmt(r["vocab_overlap"])}</td>'
            f'<td>{r["zero_shot"]:.2f}</td>'
            f'<td class="{delta_cls}">{r["rule_delta"]:+.2f}</td>'
            f'<td>{_fmt(r["consistency"])}</td>'
            f'</tr>'
        )

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    table_rows = "\n".join(row_html(r) for r in rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PatchBench Leaderboard</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.25rem; }}
  .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  #filter-wrap {{ margin-bottom: 1rem; }}
  #filter {{ width: 100%; max-width: 420px; padding: 0.45rem 0.7rem; font-size: 1rem;
             border: 1px solid #ccc; border-radius: 4px; }}
  #filter-count {{ margin-left: 0.75rem; color: #666; font-size: 0.9rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
  th {{ background: #f4f4f4; text-align: left; padding: 0.5rem 0.75rem;
        border-bottom: 2px solid #ddd; white-space: nowrap; cursor: pointer; user-select: none; }}
  th:hover {{ background: #e8e8e8; }}
  td {{ padding: 0.4rem 0.75rem; border-bottom: 1px solid #eee; }}
  tr:hover td {{ background: #fafafa; }}
  tr.hidden {{ display: none; }}
  code {{ background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85rem; }}
  .positive {{ color: #1a7f37; font-weight: 600; }}
  .negative {{ color: #cf222e; font-weight: 600; }}
  a {{ color: #0969da; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .legend {{ margin-top: 2rem; font-size: 0.85rem; color: #555; }}
  .legend table {{ width: auto; }}
  .legend td, .legend th {{ padding: 0.25rem 0.6rem; }}
  .howto {{ margin-top: 2.5rem; font-size: 0.9rem; line-height: 1.6; }}
  .howto h2 {{ font-size: 1.1rem; margin-bottom: 0.5rem; border-bottom: 1px solid #ddd; padding-bottom: 0.25rem; }}
  .howto h3 {{ font-size: 0.95rem; margin: 1.2rem 0 0.4rem; }}
  .howto ol, .howto ul {{ margin: 0.4rem 0 0.4rem 1.5rem; padding: 0; }}
  .howto li {{ margin-bottom: 0.4rem; }}
  .howto code {{ background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85rem; }}
  .howto pre {{ background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 4px;
               padding: 0.75rem 1rem; overflow-x: auto; font-size: 0.83rem; margin: 0.5rem 0; }}
  .verdict-go     {{ color: #1a7f37; font-weight: 600; }}
  .verdict-partial {{ color: #9a6700; font-weight: 600; }}
  .verdict-nogo   {{ color: #cf222e; font-weight: 600; }}
</style>
</head>
<body>
<h1>PatchBench Leaderboard</h1>
<p class="meta">Generated {generated} &middot; {len(rows)} result(s) &middot;
  <a href="https://github.com/khub-ai/patchbench">khub-ai/patchbench</a></p>

<div id="filter-wrap">
  <input id="filter" type="search" placeholder="Filter by model, domain, verdict&hellip;" autofocus>
  <span id="filter-count"></span>
</div>

<table id="lb">
<thead>
<tr>
  <th>Verdict</th>
  <th>Model</th>
  <th>Domain</th>
  <th>Confusable pair</th>
  <th>Percep.</th>
  <th>VocabΔ</th>
  <th>ZeroShot</th>
  <th>RuleDelta</th>
  <th>Consist.</th>
</tr>
</thead>
<tbody id="lb-body">
{table_rows}
</tbody>
</table>

<div class="legend">
  <p><strong>Column definitions</strong></p>
  <table>
    <tr><td><strong>Percep.</strong></td><td>Feature detection accuracy (PUPIL vs VALIDATOR ground truth)</td></tr>
    <tr><td><strong>VocabΔ</strong></td><td>Vocabulary overlap with expert descriptions</td></tr>
    <tr><td><strong>ZeroShot</strong></td><td>Classification accuracy without rules injected</td></tr>
    <tr><td><strong>RuleDelta</strong></td><td>Accuracy gain from rule injection (higher = more patchable)</td></tr>
    <tr><td><strong>Consist.</strong></td><td>Fraction of images where repeated runs give the same answer</td></tr>
  </table>
  <p><strong>Verdict thresholds</strong></p>
  <table>
    <tr><td>🟢 go</td><td>Percep ≥ 0.60 AND RuleDelta ≥ 0.15 AND Consist ≥ 0.75</td></tr>
    <tr><td>🟡 partial</td><td>Above no-go floors but not all go thresholds met</td></tr>
    <tr><td>🔴 no-go</td><td>Percep &lt; 0.30 OR Consist &lt; 0.50</td></tr>
  </table>
</div>

<div class="howto">
<h2>How to use this leaderboard</h2>
<p>This leaderboard helps you decide whether Dialogic Distillation (DD) is worth attempting
for your domain and PUPIL model, before committing to the full process.</p>

<h3>Quick path &mdash; use an existing benchmark as a proxy</h3>
<ol>
  <li><strong>Find the closest domain.</strong> Browse the table for a confusable pair that resembles
  your visual classification task &mdash; same image modality, similar level of visual subtlety,
  or the same application area (e.g. another dermatology pair as a proxy for your skin-lesion task).</li>
  <li><strong>Find your model (or the nearest equivalent).</strong> If your PUPIL model appears in the
  table, read its row directly. If not, look for a model of similar size and architecture family.</li>
  <li><strong>Read the verdict:</strong>
    <ul>
      <li><span class="verdict-go">🟢 go</span> &mdash; DD is likely to work. The model perceives domain
      features, follows injected rules, and gives stable answers. Proceed with building a rule library.</li>
      <li><span class="verdict-partial">🟡 partial</span> &mdash; DD may work but will need care.
      Check which score fell short: low RuleDelta suggests simpler, shorter rule phrasing;
      low Consistency suggests using temperature=0 or majority-vote inference.</li>
      <li><span class="verdict-nogo">🔴 no-go</span> &mdash; the model lacks the visual grounding needed
      for this domain. Consider a larger model, a domain-adapted backbone, or a different PUPIL candidate.</li>
    </ul>
  </li>
  <li><strong>Check RuleDelta specifically.</strong> High Percep but low RuleDelta means the model
  sees the features but does not act on rules &mdash; prompt engineering alone is unlikely to fix this.
  Low Percep means the model is blind to the discriminating features; rules cannot compensate.</li>
</ol>

<h3>Thorough path &mdash; run the probe on your own image set</h3>
<p>Use this when no existing benchmark is close enough to your domain, or when you need a
defensible result for your specific model and data.</p>
<ol>
  <li><strong>Prepare 24 images</strong> &mdash; 12 per class, covering the confusable pair you care
  about. Include diversity in lighting, angle, and difficulty.
  See <a href="https://github.com/khub-ai/patchbench/blob/main/CONTRIBUTING.md">CONTRIBUTING.md</a>
  for the manifest format.</li>
  <li><strong>Run the probe</strong> against your PUPIL model:
  <pre>python run_probe.py --pupil-model your-org/your-model \\
    --benchmark benchmarks/your_domain/your_pair/probe_v1/manifest.json</pre></li>
  <li><strong>Interpret the result</strong> using the same verdict logic above.
  Additionally inspect the per-image breakdowns: consistent misclassifications on one class
  point to vocabulary gaps (low VocabΔ); inconsistent predictions on the same image point
  to stability problems (low Consist.).</li>
  <li><strong>If verdict is go or partial</strong>, proceed to build your rule library using the DD
  workflow in <a href="https://github.com/khub-ai/khub-knowledge-fabric">khub-ai/khub-knowledge-fabric</a>.
  Start with the failure cases the probe identified &mdash; those are the highest-value targets
  for expert rule authoring.</li>
  <li><strong>Submit your result</strong> via pull request so others with the same model can benefit.</li>
</ol>
</div>

<script>
(function () {{
  const input   = document.getElementById('filter');
  const body    = document.getElementById('lb-body');
  const counter = document.getElementById('filter-count');
  const rows    = Array.from(body.querySelectorAll('tr'));

  function update() {{
    const q = input.value.trim().toLowerCase();
    let visible = 0;
    rows.forEach(function (tr) {{
      const match = !q || tr.textContent.toLowerCase().includes(q);
      tr.classList.toggle('hidden', !match);
      if (match) visible++;
    }});
    counter.textContent = q ? visible + ' of ' + rows.length + ' shown' : '';
  }}

  input.addEventListener('input', update);
  update();
}})();
</script>
</body>
</html>"""

    path = _HERE / "leaderboard.html"
    path.write_text(html, encoding="utf-8")
    print(f"  Written: {path.name}")


if __name__ == "__main__":
    print("Collecting results...")
    rows = collect_results()
    print(f"  Found {len(rows)} result(s)")
    write_json(rows)
    write_markdown(rows)
    write_html(rows)
    print("Done.")
