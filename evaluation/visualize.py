"""Render evaluation JSON reports as a self-contained HTML/SVG dashboard."""

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, Optional


MODES = ("static", "llm", "hybrid")
MODE_LABELS = {
    "static": "Static",
    "llm": "LLM",
    "hybrid": "Hybrid",
}
MODE_COLORS = {
    "static": "#3977b8",
    "llm": "#8b61a8",
    "hybrid": "#43866b",
}
METRICS = ("precision", "recall", "f1")
METRIC_COLORS = {
    "precision": "#3977b8",
    "recall": "#e09a38",
    "f1": "#43866b",
}
METRIC_LABELS = {
    "precision": "Precision",
    "recall": "Recall",
    "f1": "F1",
}
CATEGORIES = (
    "security",
    "quality_style",
    "maintainability",
    "complexity",
    "performance",
)


def _mode_results(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Read either dataset aggregate or all-mode single-file report shapes."""
    results = report.get("aggregate") or report.get("results") or {}
    if results:
        return results

    mode = report.get("mode")
    if mode in MODES:
        return {mode: report}
    return {}


def _metric_data(mode_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(mode_result, dict):
        return {}
    nested_metrics = mode_result.get("metrics")
    if isinstance(nested_metrics, dict):
        return nested_metrics
    return mode_result


def _value_label(value: Optional[float]) -> str:
    return "N/A (not available)" if value is None else f"{value:.3f}"


def _overall_chart(results: Dict[str, Dict[str, Any]]) -> str:
    width = 1040
    plot_x = 230
    plot_width = 680
    group_height = 82
    top = 45
    height = top + len(MODES) * group_height + 50
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Precision, recall and F1 by analysis mode">',
        '<text x="16" y="26" class="chart-title">Overall metrics by mode</text>',
    ]

    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        tick_x = plot_x + int(plot_width * tick)
        parts.append(
            f'<line x1="{tick_x}" y1="{top - 5}" x2="{tick_x}" '
            f'y2="{height - 38}" class="grid" />'
        )
        parts.append(
            f'<text x="{tick_x}" y="{height - 12}" text-anchor="middle" '
            f'class="axis-label">{tick:.0%}</text>'
        )

    for mode_index, mode in enumerate(MODES):
        mode_result = results.get(mode)
        metrics = _metric_data(mode_result)
        group_y = top + mode_index * group_height
        parts.append(
            f'<text x="16" y="{group_y + 34}" class="mode-label">'
            f'{MODE_LABELS[mode]}</text>'
        )
        for metric_index, metric in enumerate(METRICS):
            y = group_y + metric_index * 21
            raw_value = metrics.get(metric)
            value = raw_value if isinstance(raw_value, (int, float)) else None
            parts.append(
                f'<text x="115" y="{y + 11}" class="small-label">'
                f'{METRIC_LABELS[metric]}</text>'
            )
            if value is None:
                parts.append(
                    f'<text x="{plot_x}" y="{y + 12}" class="na-label">'
                    'N/A (not available)</text>'
                )
                continue
            value = max(0.0, min(1.0, float(value)))
            bar_width = int(plot_width * value)
            parts.append(
                f'<rect x="{plot_x}" y="{y}" width="{bar_width}" height="12" '
                f'fill="{METRIC_COLORS[metric]}" rx="3" />'
            )
            parts.append(
                f'<text x="{plot_x + bar_width + 8}" y="{y + 11}" '
                'class="value-label">'
                f'{html.escape(_value_label(value))}</text>'
            )

    parts.append("</svg>")
    return "".join(parts)


def _category_chart(results: Dict[str, Dict[str, Any]]) -> str:
    width = 1040
    plot_x = 250
    plot_width = 650
    row_height = 82
    top = 52
    height = top + len(CATEGORIES) * row_height + 42
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Category-level F1 by analysis mode">',
        '<defs><pattern id="na-hatch" width="8" height="8" '
        'patternTransform="rotate(45)" patternUnits="userSpaceOnUse">'
        '<rect width="8" height="8" fill="#f1f3f5" />'
        '<line x1="0" y1="0" x2="0" y2="8" stroke="#aab4bf" '
        'stroke-width="3" /></pattern></defs>',
        '<text x="16" y="26" class="chart-title">Category F1 by mode</text>',
    ]

    for tick in (0.0, 0.5, 1.0):
        tick_x = plot_x + int(plot_width * tick)
        parts.append(
            f'<line x1="{tick_x}" y1="{top - 8}" x2="{tick_x}" '
            f'y2="{height - 35}" class="grid" />'
        )
        parts.append(
            f'<text x="{tick_x}" y="{height - 10}" text-anchor="middle" '
            f'class="axis-label">{tick:.0%}</text>'
        )

    # The small legend maps each bar color to an analyzer mode.
    legend_x = plot_x
    for mode in MODES:
        parts.append(
            f'<rect x="{legend_x}" y="32" width="10" height="10" '
            f'fill="{MODE_COLORS[mode]}" rx="2" />'
        )
        parts.append(
            f'<text x="{legend_x + 15}" y="41" class="small-label">'
            f'{MODE_LABELS[mode]}</text>'
        )
        legend_x += 105

    for category_index, category in enumerate(CATEGORIES):
        row_y = top + category_index * row_height
        category_metrics = {
            mode: (results.get(mode) or {}).get("category_metrics", {}).get(category)
            for mode in MODES
        }
        known_ground_truth = [
            metrics.get("tp", 0) + metrics.get("fn", 0)
            for metrics in category_metrics.values()
            if isinstance(metrics, dict)
            and isinstance(metrics.get("tp"), (int, float))
            and isinstance(metrics.get("fn"), (int, float))
        ]
        has_ground_truth = any(count > 0 for count in known_ground_truth)
        parts.append(
            f'<text x="16" y="{row_y + 28}" class="category-label">'
            f'{html.escape(category)}</text>'
        )

        for mode_index, mode in enumerate(MODES):
            y = row_y + mode_index * 19
            mode_result = results.get(mode)
            metrics = category_metrics[mode]
            if not mode_result:
                parts.append(
                    f'<text x="{plot_x}" y="{y + 11}" class="na-label">'
                    'N/A (mode unavailable)</text>'
                )
                continue
            if not has_ground_truth:
                parts.append(
                    f'<rect x="{plot_x}" y="{y}" width="{plot_width}" height="12" '
                    'fill="url(#na-hatch)" rx="3" />'
                )
                parts.append(
                    f'<text x="{plot_x + 9}" y="{y + 11}" class="na-label">'
                    'N/A (no ground-truth examples)</text>'
                )
                continue
            if not isinstance(metrics, dict) or not isinstance(metrics.get("f1"), (int, float)):
                parts.append(
                    f'<text x="{plot_x}" y="{y + 11}" class="na-label">'
                    'N/A (category metric unavailable)</text>'
                )
                continue

            value = max(0.0, min(1.0, float(metrics["f1"])))
            bar_width = int(plot_width * value)
            parts.append(
                f'<rect x="{plot_x}" y="{y}" width="{bar_width}" height="12" '
                f'fill="{MODE_COLORS[mode]}" rx="3" />'
            )
            parts.append(
                f'<text x="{plot_x + bar_width + 8}" y="{y + 11}" '
                'class="value-label">'
                f'{html.escape(_value_label(value))}</text>'
            )

    parts.append("</svg>")
    return "".join(parts)


def build_visualization_html(report: Dict[str, Any]) -> str:
    """Build a self-contained dashboard from an evaluation report dictionary."""
    results = _mode_results(report)
    provider = str(report.get("provider", "unknown")).strip().lower()
    if provider == "mock":
        provider_notice = (
            "MOCK RESULTS — for pipeline verification only; "
            "these are not real Gemini performance results."
        )
    else:
        provider_notice = f"Evaluation provider: {html.escape(provider)}"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Code Quality Evaluation Dashboard</title>
  <style>
    :root {{ color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #202a35; background: #f5f7fa; }}
    body {{ margin: 0; padding: 32px; }}
    main {{ max-width: 1120px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .notice {{ padding: 12px 16px; border-left: 4px solid #bd7b1c; background: #fff5df; font-weight: 650; }}
    .card {{ margin-top: 22px; padding: 18px; overflow-x: auto; border: 1px solid #dfe5eb; border-radius: 12px; background: white; box-shadow: 0 2px 8px #1c2c3a0a; }}
    svg {{ display: block; min-width: 760px; width: 100%; height: auto; }}
    .chart-title {{ font-size: 16px; font-weight: 700; fill: #263443; }}
    .mode-label, .category-label {{ font-size: 13px; font-weight: 650; fill: #263443; }}
    .small-label, .axis-label {{ font-size: 11px; fill: #596675; }}
    .value-label {{ font-size: 11px; fill: #263443; }}
    .na-label {{ font-size: 11px; fill: #56616d; font-style: italic; }}
    .grid {{ stroke: #e2e7ec; stroke-width: 1; }}
    .footnote {{ color: #596675; font-size: 13px; line-height: 1.5; }}
    @media (max-width: 640px) {{ body {{ padding: 16px; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Code Quality Evaluation Dashboard</h1>
    <p class="notice">{provider_notice}</p>
    <section class="card">{_overall_chart(results)}</section>
    <section class="card">{_category_chart(results)}</section>
    <p class="footnote">Category F1 is shown as unavailable when the evaluated labels contain no ground-truth examples for that category. A displayed 0.000 is a calculated score, not a missing value.</p>
  </main>
</body>
</html>
"""


def load_report(report_path: Path) -> Dict[str, Any]:
    with report_path.open("r", encoding="utf-8") as report_file:
        report = json.load(report_file)
    if not isinstance(report, dict):
        raise ValueError("Evaluation report must contain a JSON object.")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an HTML visualization from an evaluation JSON report."
    )
    parser.add_argument("report", type=Path, help="Evaluation report JSON file")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="HTML output path (defaults to the report filename with .html)",
    )
    args = parser.parse_args()

    report = load_report(args.report)
    output_path = args.output or args.report.with_suffix(".html")
    output_path.write_text(build_visualization_html(report), encoding="utf-8")
    print(f"Visualization saved to: {output_path}")


if __name__ == "__main__":
    main()
