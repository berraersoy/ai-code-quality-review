"""
Evaluation module for AI-Assisted Code Quality Review Tool.
"""

from evaluation.ground_truth import (
    get_ground_truth_for_file,
    load_ground_truth,
    validate_ground_truth_item,
)
from evaluation.metrics import (
    aggregate_metrics,
    calculate_metrics,
    format_metrics,
)


def __getattr__(name):
    if name in {
        "compare_modes_for_file",
        "evaluate_dataset",
        "evaluate_file",
        "evaluate_findings",
        "match_predictions_with_ground_truth",
    }:
        import evaluation.evaluator as evaluator_module
        return getattr(evaluator_module, name)
    raise AttributeError(f"module 'evaluation' has no attribute '{name}'")


__all__ = [
    "load_ground_truth",
    "get_ground_truth_for_file",
    "validate_ground_truth_item",
    "calculate_metrics",
    "aggregate_metrics",
    "format_metrics",
    "match_predictions_with_ground_truth",
    "evaluate_findings",
    "evaluate_file",
    "compare_modes_for_file",
    "evaluate_dataset",
]
