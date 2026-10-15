"""
Evaluation framework for comparing Static, LLM, and Hybrid code analysis.

ACADEMIC CONSTRAINTS & PRINCIPLES:
1. Ground truth represents human-curated benchmarks and is never derived
   automatically from static or LLM analyzer outputs.
2. Predictions and ground-truth issues are matched strictly one-to-one.
3. Multi-file aggregate metrics use micro-averaging: raw TP, FP, and FN
   are summed first, then overall Precision, Recall, and F1 are calculated.
4. Static, LLM, and Hybrid modes remain independent and comparable.
"""

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from analyzer.hybrid_analyzer import run_hybrid_analysis
from analyzer.llm_analyzer import analyze_with_llm
from analyzer.static_analyzer import analyze_file
from evaluation.ground_truth import (
    VALID_CATEGORIES,
    get_ground_truth_for_file,
    load_ground_truth,
)
from evaluation.metrics import (
    aggregate_category_metrics,
    aggregate_metrics,
    calculate_category_metrics,
    calculate_metrics,
    format_metrics,
)


CATEGORY_ORDER = tuple(sorted(VALID_CATEGORIES))


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_EVALUATION_CONFIG = {
    "category_weight": 0.40,
    "line_weight": 0.35,
    "text_weight": 0.25,
    "min_match_threshold": 0.45,
    "min_category_similarity": 0.50,
    "max_line_distance": 3,
    "min_text_similarity": 0.15,
}

CATEGORY_COMPATIBILITY = {
    frozenset({"quality_style", "maintainability"}): 0.60,
    frozenset({"maintainability", "complexity"}): 0.50,
}


# ============================================================
# SIMILARITY FUNCTIONS
# ============================================================

def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip punctuation and whitespace."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def compute_category_similarity(cat1: str, cat2: str) -> float:
    """
    Calculate compatibility between predicted category and ground-truth category.
    Strictly forbids security issues from matching non-security issues.
    """
    c1 = (cat1 or "").strip().lower()
    c2 = (cat2 or "").strip().lower()

    if not c1 or not c2:
        return 0.0

    if c1 == c2:
        return 1.0

    # Check known related categories
    pair = frozenset({c1, c2})
    if pair in CATEGORY_COMPATIBILITY:
        return CATEGORY_COMPATIBILITY[pair]

    return 0.0


def compute_line_similarity(line1: int, line2: int, max_distance: int = 3) -> float:
    """
    Calculate similarity based on line distance.
    Returns 0.0 if distance exceeds max_distance.
    """
    if not isinstance(line1, int) or not isinstance(line2, int):
        return 0.0

    diff = abs(line1 - line2)
    if diff > max_distance:
        return 0.0

    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.8
    if diff == 2:
        return 0.5
    if diff == 3:
        return 0.2

    return 0.0


def compute_text_similarity(text1: str, text2: str) -> float:
    """
    Compute similarity between predicted message and ground-truth description
    using both SequenceMatcher and token Jaccard overlap.
    """
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    if not norm1 or not norm2:
        return 0.0

    seq_ratio = SequenceMatcher(None, norm1, norm2).ratio()

    tokens1 = set(norm1.split())
    tokens2 = set(norm2.split())
    union = tokens1 | tokens2
    jaccard = (len(tokens1 & tokens2) / len(union)) if union else 0.0

    return max(seq_ratio, jaccard)


def calculate_evaluation_match_score(
    prediction: Dict[str, Any],
    ground_truth: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate weighted match score and similarity components between
    a predicted finding and a ground-truth item.
    """
    pred_cat = str(prediction.get("category", "")).strip().lower()
    gt_cat = str(ground_truth.get("category", "")).strip().lower()
    cat_sim = compute_category_similarity(pred_cat, gt_cat)

    pred_line = prediction.get("line", 0)
    gt_line = ground_truth.get("line", 0)
    line_sim = compute_line_similarity(
        pred_line,
        gt_line,
        max_distance=config["max_line_distance"]
    )

    pred_text = str(
        prediction.get("message")
        or prediction.get("explanation")
        or ""
    )
    gt_text = str(ground_truth.get("description", ""))
    text_sim = compute_text_similarity(pred_text, gt_text)

    score = (
        config["category_weight"] * cat_sim
        + config["line_weight"] * line_sim
        + config["text_weight"] * text_sim
    )

    details = {
        "score": score,
        "category_similarity": cat_sim,
        "line_similarity": line_sim,
        "text_similarity": text_sim
    }

    return score, details


def is_valid_evaluation_match(
    score: float,
    details: Dict[str, float],
    config: Dict[str, Any]
) -> bool:
    """
    Verify whether a match candidate meets all minimum thresholds.
    """
    if score < config["min_match_threshold"]:
        return False
    if details["category_similarity"] < config["min_category_similarity"]:
        return False
    if details["line_similarity"] <= 0.0:
        return False
    if details["text_similarity"] < config["min_text_similarity"]:
        return False
    return True


# ============================================================
# ONE-TO-ONE MATCHING
# ============================================================

def match_predictions_with_ground_truth(
    predictions: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Perform greedy one-to-one bipartite matching between predictions and ground truth.

    Guarantees:
    - Each prediction matches at most one ground-truth item.
    - Each ground-truth item is matched by at most one prediction.
    - Matches are selected by highest match score first.
    """
    active_config = dict(DEFAULT_EVALUATION_CONFIG)
    if config:
        active_config.update(config)

    # Build candidate matches
    candidates = []
    for pred_idx, pred in enumerate(predictions):
        for gt_idx, gt in enumerate(ground_truth):
            score, details = calculate_evaluation_match_score(
                pred,
                gt,
                active_config
            )
            if is_valid_evaluation_match(score, details, active_config):
                candidates.append((score, pred_idx, gt_idx, details))

    # Sort candidates by score descending
    candidates.sort(key=lambda c: c[0], reverse=True)

    used_preds: Set[int] = set()
    used_gts: Set[int] = set()
    matches = []

    for score, p_idx, g_idx, details in candidates:
        if p_idx in used_preds or g_idx in used_gts:
            continue

        pred = predictions[p_idx]
        gt = ground_truth[g_idx]

        matches.append({
            "ground_truth_id": gt.get("id"),
            "ground_truth_category": gt.get("category"),
            "ground_truth_line": gt.get("line"),
            "ground_truth_description": gt.get("description"),
            "prediction_tool": pred.get("tool") or pred.get("static_tool") or "unknown",
            "prediction_source": pred.get("source", "unknown"),
            "prediction_code": pred.get("code") or pred.get("static_code") or pred.get("llm_code") or "UNKNOWN",
            "prediction_category": pred.get("category"),
            "prediction_line": pred.get("line"),
            "prediction_message": pred.get("message"),
            "match_score": round(score, 4),
            "match_details": {
                k: round(v, 4) for k, v in details.items()
            }
        })

        used_preds.add(p_idx)
        used_gts.add(g_idx)

    # Determine False Positives (unmatched predictions)
    false_positives = [
        pred
        for idx, pred in enumerate(predictions)
        if idx not in used_preds
    ]

    # Determine False Negatives (unmatched ground-truth items)
    false_negatives = [
        gt
        for idx, gt in enumerate(ground_truth)
        if idx not in used_gts
    ]

    tp = len(matches)
    fp = len(false_positives)
    fn = len(false_negatives)

    metrics = calculate_metrics(tp, fp, fn)

    return {
        "metrics": metrics,
        "matches": matches,
        "false_positives": false_positives,
        "false_negatives": false_negatives
    }


# ============================================================
# EVALUATION RUNNERS
# ============================================================

def evaluate_findings(
    predictions: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]],
    file_path: Optional[str] = None,
    mode: str = "custom",
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluate a list of findings directly against a ground-truth list.
    """
    match_result = match_predictions_with_ground_truth(
        predictions,
        ground_truth,
        config=config
    )

    return {
        "file": file_path,
        "mode": mode,
        "total_predictions": len(predictions),
        "total_ground_truth": len(ground_truth),
        "metrics": match_result["metrics"],
        "category_metrics": calculate_category_metrics(
            match_result["matches"],
            match_result["false_positives"],
            match_result["false_negatives"],
            CATEGORY_ORDER,
        ),
        "matches": match_result["matches"],
        "false_positives": match_result["false_positives"],
        "false_negatives": match_result["false_negatives"]
    }


def evaluate_file(
    file_path: str,
    ground_truth: Optional[List[Dict[str, Any]]] = None,
    mode: str = "hybrid",
    provider: str = "mock",
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Run an analyzer in the specified mode on file_path and evaluate findings
    against ground truth.
    """
    if ground_truth is None:
        ground_truth = get_ground_truth_for_file(file_path)

    if mode == "static":
        report = analyze_file(file_path)
    elif mode == "llm":
        report = analyze_with_llm(file_path, provider=provider)
    elif mode == "hybrid":
        report = run_hybrid_analysis(file_path, provider=provider)
    else:
        raise ValueError(f"Unsupported evaluation mode: {mode}")

    predictions = report.get("findings", [])

    return evaluate_findings(
        predictions=predictions,
        ground_truth=ground_truth,
        file_path=file_path,
        mode=mode,
        config=config
    )


def compare_modes_for_file(
    file_path: str,
    ground_truth: Optional[List[Dict[str, Any]]] = None,
    provider: str = "mock",
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Run and compare Static, LLM, and Hybrid analysis modes on a single file.
    """
    if ground_truth is None:
        ground_truth = get_ground_truth_for_file(file_path)

    static_eval = evaluate_file(
        file_path,
        ground_truth=ground_truth,
        mode="static",
        provider=provider,
        config=config
    )

    llm_eval = evaluate_file(
        file_path,
        ground_truth=ground_truth,
        mode="llm",
        provider=provider,
        config=config
    )

    hybrid_eval = evaluate_file(
        file_path,
        ground_truth=ground_truth,
        mode="hybrid",
        provider=provider,
        config=config
    )

    return {
        "file": file_path,
        "ground_truth_count": len(ground_truth),
        "results": {
            "static": static_eval,
            "llm": llm_eval,
            "hybrid": hybrid_eval
        }
    }


def evaluate_dataset(
    file_paths: Optional[List[str]] = None,
    ground_truth_dataset: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    provider: str = "mock",
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluate multiple files across all three modes and produce micro-averaged
    aggregate metrics across the dataset.
    """
    if ground_truth_dataset is None:
        ground_truth_dataset = load_ground_truth()

    if file_paths is None:
        file_paths = list(ground_truth_dataset.keys())

    per_file: Dict[str, Any] = {}

    static_metrics_list = []
    llm_metrics_list = []
    hybrid_metrics_list = []

    for file_path in file_paths:
        file_gt = get_ground_truth_for_file(
            file_path,
            ground_truth_dataset=ground_truth_dataset
        )

        file_comparison = compare_modes_for_file(
            file_path,
            ground_truth=file_gt,
            provider=provider,
            config=config
        )
        per_file[file_path] = file_comparison

        static_metrics_list.append(
            file_comparison["results"]["static"]["metrics"]
        )
        llm_metrics_list.append(
            file_comparison["results"]["llm"]["metrics"]
        )
        hybrid_metrics_list.append(
            file_comparison["results"]["hybrid"]["metrics"]
        )

    # Micro-average: sum raw TP, FP, FN first!
    aggregate = {}
    for mode, metrics_list in (
        ("static", static_metrics_list),
        ("llm", llm_metrics_list),
        ("hybrid", hybrid_metrics_list),
    ):
        aggregate[mode] = aggregate_metrics(metrics_list)
        aggregate[mode]["category_metrics"] = aggregate_category_metrics(
            [
                file_comparison["results"][mode]["category_metrics"]
                for file_comparison in per_file.values()
            ],
            CATEGORY_ORDER,
        )

    return {
        "files_evaluated": len(file_paths),
        "provider": provider,
        "aggregate": aggregate,
        "per_file": per_file
    }


# ============================================================
# CLI PRESENTATION HELPERS
# ============================================================

def format_category_summary_table(
    category_metrics: Dict[str, Dict[str, Any]],
    mode: str = ""
) -> str:
    """Format category-level metrics for console display."""
    lines = [
        "\nCategory-level metrics",
        f"{'Mode':<10} | {'Category':<18} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'Precision':<10} | {'Recall':<10} | {'F1':<10}",
        "-" * 100,
    ]

    for category, metrics in category_metrics.items():
        lines.append(
            f"{mode:<10} | {category:<18} | {metrics['tp']:<4} | {metrics['fp']:<4} | "
            f"{metrics['fn']:<4} | {metrics['precision']:<10.4f} | "
            f"{metrics['recall']:<10.4f} | {metrics['f1']:<10.4f}"
        )

    return "\n".join(lines)


def format_summary_table(comparison_or_aggregate: Dict[str, Any]) -> str:
    """Format evaluation comparison table for console display."""
    lines = [
        "",
        f"{'Mode':<10} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'Precision':<10} | {'Recall':<10} | {'F1':<10}",
        "-" * 68
    ]

    results = comparison_or_aggregate.get("results") or comparison_or_aggregate

    for mode in ("static", "llm", "hybrid"):
        mode_data = results.get(mode, {})
        metrics = mode_data.get("metrics") or mode_data
        tp = metrics.get("tp", 0)
        fp = metrics.get("fp", 0)
        fn = metrics.get("fn", 0)
        p = metrics.get("precision", 0.0)
        r = metrics.get("recall", 0.0)
        f1 = metrics.get("f1", 0.0)

        lines.append(
            f"{mode:<10} | {tp:<4} | {fp:<4} | {fn:<4} | {p:<10.4f} | {r:<10.4f} | {f1:<10.4f}"
        )

    if any(
        results.get(mode, {}).get("category_metrics")
        for mode in ("static", "llm", "hybrid")
    ):
        lines.extend([
            "",
            "Category-level metrics",
            f"{'Mode':<10} | {'Category':<18} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'Precision':<10} | {'Recall':<10} | {'F1':<10}",
            "-" * 100,
        ])
        for mode in ("static", "llm", "hybrid"):
            mode_data = results.get(mode, {})
            for category, metrics in mode_data.get("category_metrics", {}).items():
                lines.append(
                    f"{mode:<10} | {category:<18} | {metrics['tp']:<4} | {metrics['fp']:<4} | "
                    f"{metrics['fn']:<4} | {metrics['precision']:<10.4f} | "
                    f"{metrics['recall']:<10.4f} | {metrics['f1']:<10.4f}"
                )

    lines.append("")
    return "\n".join(lines)


# ============================================================
# CLI ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="AI-Assisted Code Quality Review - Evaluation Module"
    )

    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Source file to evaluate (e.g. samples/bad_code.py)"
    )

    parser.add_argument(
        "--mode",
        choices=["static", "llm", "hybrid", "all"],
        default="all",
        help="Evaluation mode (default: all)"
    )

    parser.add_argument(
        "--provider",
        choices=["mock", "gemini"],
        default="mock",
        help="LLM provider (default: mock)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all files in ground_truth.json"
    )

    parser.add_argument(
        "--ground-truth",
        default=None,
        help="Custom ground truth JSON file"
    )

    parser.add_argument(
        "--output",
        default=None,
        help="Save evaluation report to JSON file"
    )

    args = parser.parse_args()

    gt_dataset = load_ground_truth(args.ground_truth)

    if args.all or args.file is None:
        report = evaluate_dataset(
            ground_truth_dataset=gt_dataset,
            provider=args.provider
        )
        print("\n=== DATASET EVALUATION RESULTS (AGGREGATE) ===")
        print(format_summary_table(report["aggregate"]))
    else:
        if args.mode == "all":
            report = compare_modes_for_file(
                args.file,
                provider=args.provider
            )
            print(f"\n=== EVALUATION RESULTS FOR: {args.file} ===")
            print(format_summary_table(report["results"]))
        else:
            report = evaluate_file(
                args.file,
                mode=args.mode,
                provider=args.provider
            )
            m = report["metrics"]
            print(f"\n=== EVALUATION RESULT: {args.file} ({args.mode}) ===")
            print(
                f"TP: {m['tp']} | FP: {m['fp']} | FN: {m['fn']} | "
                f"Precision: {m['precision']:.4f} | Recall: {m['recall']:.4f} | F1: {m['f1']:.4f}"
            )
            print(format_category_summary_table(report["category_metrics"]))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        print(f"Report saved to: {args.output}")


if __name__ == "__main__":
    main()
