"""
Evaluation metrics calculation module.

Provides standard academic classification metrics:
- True Positives (TP): Correctly identified ground-truth defects.
- False Positives (FP): Predicted findings not corresponding to real defects.
- False Negatives (FN): Ground-truth defects missed by the analyzer.
- Precision: TP / (TP + FP)
- Recall: TP / (TP + FN)
- F1 Score: 2 * Precision * Recall / (Precision + Recall)

Zero-division cases are handled safely by returning 0.0.
Floating-point precision is maintained internally; rounding only occurs upon formatting.
"""

from typing import Any, Dict, List, Sequence


def calculate_metrics(tp: int, fp: int, fn: int) -> Dict[str, Any]:
    """
    Calculate classification metrics from TP, FP, FN counts.

    Handles zero denominators safely (returns 0.0).
    Maintains full floating-point precision internally.
    """
    precision = (
        float(tp) / float(tp + fp)
        if (tp + fp) > 0
        else 0.0
    )

    recall = (
        float(tp) / float(tp + fn)
        if (tp + fn) > 0
        else 0.0
    )

    f1 = (
        (2.0 * precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "precision": precision,
        "recall": recall,
        "f1": f1
    }


def aggregate_metrics(metrics_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate counts across multiple files or runs using micro-averaging.

    ACADEMIC REQUIREMENT:
    Raw TP, FP, and FN are summed across all files FIRST, and then
    overall precision, recall, and F1 are calculated from the totals.
    Per-file F1 scores are never averaged directly.
    """
    total_tp = sum(m.get("tp", 0) for m in metrics_list)
    total_fp = sum(m.get("fp", 0) for m in metrics_list)
    total_fn = sum(m.get("fn", 0) for m in metrics_list)

    return calculate_metrics(total_tp, total_fp, total_fn)


def calculate_category_metrics(
    matches: List[Dict[str, Any]],
    false_positives: List[Dict[str, Any]],
    false_negatives: List[Dict[str, Any]],
    categories: Sequence[str]
) -> Dict[str, Dict[str, Any]]:
    """Calculate metrics for each category using one-to-one match results.

    Matched findings are assigned to the ground-truth category. Unmatched
    predictions use their predicted category, and unmatched labels use their
    ground-truth category. Unsupported or missing categories are excluded from
    category totals but remain included in the overall metrics.
    """
    counts = {
        category: {"tp": 0, "fp": 0, "fn": 0}
        for category in categories
    }

    def normalized_category(value: Any) -> str:
        return str(value or "").strip().lower()

    for match in matches:
        category = normalized_category(
            match.get("ground_truth_category")
        )
        if category in counts:
            counts[category]["tp"] += 1

    for finding in false_positives:
        category = normalized_category(finding.get("category"))
        if category in counts:
            counts[category]["fp"] += 1

    for finding in false_negatives:
        category = normalized_category(finding.get("category"))
        if category in counts:
            counts[category]["fn"] += 1

    return {
        category: calculate_metrics(**category_counts)
        for category, category_counts in counts.items()
    }


def aggregate_category_metrics(
    category_metrics_list: List[Dict[str, Dict[str, Any]]],
    categories: Sequence[str]
) -> Dict[str, Dict[str, Any]]:
    """Micro-average category metrics by summing each category's raw counts."""
    return {
        category: aggregate_metrics([
            metrics.get(category, {})
            for metrics in category_metrics_list
        ])
        for category in categories
    }


def format_metrics(metrics: Dict[str, Any], digits: int = 4) -> Dict[str, Any]:
    """
    Return a formatted copy of the metrics dictionary for display or reporting.
    """
    formatted = dict(metrics)
    for key in ("precision", "recall", "f1"):
        if key in formatted and isinstance(formatted[key], (int, float)):
            formatted[key] = round(formatted[key], digits)
    return formatted
