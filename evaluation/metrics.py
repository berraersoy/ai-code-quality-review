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

from typing import Any, Dict, List


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


def format_metrics(metrics: Dict[str, Any], digits: int = 4) -> Dict[str, Any]:
    """
    Return a formatted copy of the metrics dictionary for display or reporting.
    """
    formatted = dict(metrics)
    for key in ("precision", "recall", "f1"):
        if key in formatted and isinstance(formatted[key], (int, float)):
            formatted[key] = round(formatted[key], digits)
    return formatted
