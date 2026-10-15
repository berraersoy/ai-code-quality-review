import pytest

from evaluation.evaluator import (
    compare_modes_for_file,
    compute_category_similarity,
    compute_line_similarity,
    evaluate_dataset,
    evaluate_file,
    evaluate_findings,
    match_predictions_with_ground_truth,
)
from evaluation.ground_truth import (
    get_ground_truth_for_file,
    load_ground_truth,
    validate_ground_truth_item,
)
from evaluation.metrics import (
    aggregate_category_metrics,
    aggregate_metrics,
    calculate_metrics,
    format_metrics,
)


# ============================================================
# FIXTURES & HELPERS
# ============================================================

def _make_gt(id_="GT-001", category="security", line=4, severity="high", desc="Hardcoded password"):
    return {
        "id": id_,
        "category": category,
        "line": line,
        "severity": severity,
        "description": desc
    }


def _make_pred(tool="bandit", category="security", line=4, code="B105", message="Possible hardcoded password"):
    return {
        "tool": tool,
        "category": category,
        "line": line,
        "code": code,
        "severity": "medium",
        "message": message,
        "source": "static"
    }


# ============================================================
# METRICS UNIT TESTS
# ============================================================

def test_metrics_perfect_prediction():
    res = calculate_metrics(tp=5, fp=0, fn=0)
    assert res["tp"] == 5
    assert res["fp"] == 0
    assert res["fn"] == 0
    assert res["precision"] == 1.0
    assert res["recall"] == 1.0
    assert res["f1"] == 1.0


def test_metrics_one_false_positive():
    res = calculate_metrics(tp=2, fp=1, fn=0)
    assert res["tp"] == 2
    assert res["fp"] == 1
    assert res["fn"] == 0
    assert pytest.approx(res["precision"]) == 2.0 / 3.0
    assert res["recall"] == 1.0
    assert pytest.approx(res["f1"]) == 0.8


def test_metrics_one_false_negative():
    res = calculate_metrics(tp=2, fp=0, fn=1)
    assert res["tp"] == 2
    assert res["fp"] == 0
    assert res["fn"] == 1
    assert res["precision"] == 1.0
    assert pytest.approx(res["recall"]) == 2.0 / 3.0
    assert pytest.approx(res["f1"]) == 0.8


def test_metrics_empty_predictions():
    # 0 predictions made when 3 defects exist
    res = calculate_metrics(tp=0, fp=0, fn=3)
    assert res["tp"] == 0
    assert res["fp"] == 0
    assert res["fn"] == 3
    assert res["precision"] == 0.0
    assert res["recall"] == 0.0
    assert res["f1"] == 0.0


def test_metrics_empty_ground_truth():
    # 4 predictions made when 0 ground truth defects exist
    res = calculate_metrics(tp=0, fp=4, fn=0)
    assert res["tp"] == 0
    assert res["fp"] == 4
    assert res["fn"] == 0
    assert res["precision"] == 0.0
    assert res["recall"] == 0.0
    assert res["f1"] == 0.0


def test_metrics_all_zero():
    res = calculate_metrics(tp=0, fp=0, fn=0)
    assert res["precision"] == 0.0
    assert res["recall"] == 0.0
    assert res["f1"] == 0.0


def test_aggregate_metrics_uses_micro_averaging_not_macro_average():
    # File 1: TP=1, FP=0, FN=0 -> Precision=1, Recall=1, F1=1.0
    # File 2: TP=1, FP=9, FN=0 -> Precision=0.1, Recall=1, F1=0.1818
    # Direct average of F1s would be (1.0 + 0.1818)/2 = 0.5909
    # Micro-average: Total TP=2, Total FP=9, Total FN=0 -> Precision=2/11 = 0.1818, Recall=1.0, F1=0.3077
    m1 = calculate_metrics(tp=1, fp=0, fn=0)
    m2 = calculate_metrics(tp=1, fp=9, fn=0)

    agg = aggregate_metrics([m1, m2])
    assert agg["tp"] == 2
    assert agg["fp"] == 9
    assert agg["fn"] == 0
    assert pytest.approx(agg["precision"]) == 2.0 / 11.0
    assert agg["recall"] == 1.0
    # F1 must NOT equal the average of individual F1s
    macro_f1 = (m1["f1"] + m2["f1"]) / 2.0
    assert agg["f1"] != macro_f1
    assert pytest.approx(agg["f1"]) == (2 * (2 / 11) * 1) / ((2 / 11) + 1)


def test_format_metrics_rounds_floats():
    m = calculate_metrics(tp=1, fp=2, fn=0)
    formatted = format_metrics(m, digits=2)
    assert formatted["precision"] == 0.33
    assert formatted["recall"] == 1.0
    assert formatted["f1"] == 0.5


def test_category_metrics_count_tp_fp_fn_and_calculate_rates():
    ground_truth = [
        _make_gt(id_="GT-SEC", category="security", line=4, desc="Hardcoded password"),
        _make_gt(id_="GT-CPLX", category="complexity", line=8, desc="Cyclomatic complexity"),
        _make_gt(id_="GT-MNT", category="maintainability", line=10, desc="Nested conditions"),
    ]
    predictions = [
        _make_pred(category="security", line=4, message="Hardcoded password in source"),
        _make_pred(category="complexity", line=8, message="Cyclomatic complexity is elevated"),
        _make_pred(category="security", line=30, message="Unrelated security finding"),
        _make_pred(category="performance", line=20, message="Repeated work in a loop"),
    ]

    result = evaluate_findings(predictions, ground_truth)
    categories = result["category_metrics"]

    security = categories["security"]
    assert (security["tp"], security["fp"], security["fn"]) == (1, 1, 0)
    assert security["precision"] == 0.5
    assert security["recall"] == 1.0
    assert security["f1"] == pytest.approx(2.0 / 3.0)

    complexity = categories["complexity"]
    assert (complexity["tp"], complexity["fp"], complexity["fn"]) == (1, 0, 0)
    assert complexity["precision"] == complexity["recall"] == complexity["f1"] == 1.0

    maintainability = categories["maintainability"]
    assert (maintainability["tp"], maintainability["fp"], maintainability["fn"]) == (0, 0, 1)
    assert maintainability["recall"] == maintainability["f1"] == 0.0

    performance = categories["performance"]
    assert (performance["tp"], performance["fp"], performance["fn"]) == (0, 1, 0)
    assert performance["precision"] == performance["recall"] == performance["f1"] == 0.0


def test_category_aggregation_uses_micro_averaging():
    first_file = {"security": calculate_metrics(tp=1, fp=0, fn=0)}
    second_file = {"security": calculate_metrics(tp=1, fp=9, fn=0)}

    aggregate = aggregate_category_metrics(
        [first_file, second_file],
        categories=("security",),
    )["security"]

    assert aggregate["tp"] == 2
    assert aggregate["fp"] == 9
    assert aggregate["fn"] == 0
    assert aggregate["precision"] == pytest.approx(2.0 / 11.0)
    assert aggregate["recall"] == 1.0
    assert aggregate["f1"] == pytest.approx(4.0 / 13.0)


def test_category_metrics_include_empty_supported_categories_safely():
    result = evaluate_findings(predictions=[], ground_truth=[])

    assert set(result["category_metrics"]) == {
        "security",
        "quality_style",
        "maintainability",
        "complexity",
        "performance",
    }
    for metrics in result["category_metrics"].values():
        assert metrics == {
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
        }


def test_category_metrics_preserve_existing_overall_report_shape():
    result = evaluate_findings(
        predictions=[_make_pred()],
        ground_truth=[_make_gt()],
    )

    assert result["metrics"] == {
        "tp": 1,
        "fp": 0,
        "fn": 0,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }
    assert set(result["category_metrics"]["security"]) == set(result["metrics"])


# ============================================================
# GROUND TRUTH UNIT TESTS
# ============================================================

def test_load_ground_truth_loads_valid_dataset():
    gt = load_ground_truth("evaluation_dataset/ground_truth.json")
    assert "samples/bad_code.py" in gt
    assert len(gt["samples/bad_code.py"]) >= 3


def test_get_ground_truth_for_file_handles_variations():
    items = get_ground_truth_for_file("samples/bad_code.py")
    assert len(items) >= 3

    items_basename = get_ground_truth_for_file("bad_code.py")
    assert len(items_basename) == len(items)


def test_validate_ground_truth_item_rejects_malformed():
    assert validate_ground_truth_item({"invalid": "structure"}) is False
    assert validate_ground_truth_item(_make_gt(line=0)) is False
    assert validate_ground_truth_item(_make_gt(category="invalid_cat")) is False
    assert validate_ground_truth_item(_make_gt(severity="invalid_sev")) is False


# ============================================================
# ONE-TO-ONE MATCHING & EVALUATOR TESTS
# ============================================================

def test_matching_perfect_pair():
    gt = [_make_gt(id_="GT-001", category="security", line=4, desc="Hardcoded password")]
    pred = [_make_pred(tool="bandit", category="security", line=4, message="Possible hardcoded password: 'admin123'")]

    result = match_predictions_with_ground_truth(pred, gt)
    assert result["metrics"]["tp"] == 1
    assert result["metrics"]["fp"] == 0
    assert result["metrics"]["fn"] == 0
    assert result["metrics"]["precision"] == 1.0
    assert result["metrics"]["recall"] == 1.0
    assert len(result["matches"]) == 1
    assert result["matches"][0]["ground_truth_id"] == "GT-001"


def test_matching_one_prediction_cannot_match_multiple_ground_truths():
    # Two ground truth items on line 4
    gt = [
        _make_gt(id_="GT-001", category="security", line=4, desc="Hardcoded password"),
        _make_gt(id_="GT-002", category="security", line=4, desc="Password exposure risk"),
    ]
    # Only one prediction
    pred = [
        _make_pred(tool="bandit", category="security", line=4, message="Possible hardcoded password: 'admin123'")
    ]

    result = match_predictions_with_ground_truth(pred, gt)
    assert result["metrics"]["tp"] == 1
    assert result["metrics"]["fp"] == 0
    assert result["metrics"]["fn"] == 1  # The second GT remains unmatched!
    assert len(result["matches"]) == 1


def test_matching_one_ground_truth_cannot_match_multiple_predictions():
    # One ground truth item on line 4
    gt = [
        _make_gt(id_="GT-001", category="security", line=4, desc="Hardcoded password")
    ]
    # Two predictions targeting line 4
    pred = [
        _make_pred(tool="bandit", category="security", line=4, code="B105", message="Hardcoded password"),
        _make_pred(tool="llm", category="security", line=4, code="LLM-SEC", message="Password in source code"),
    ]

    result = match_predictions_with_ground_truth(pred, gt)
    assert result["metrics"]["tp"] == 1  # Only 1 prediction can match the 1 GT!
    assert result["metrics"]["fp"] == 1  # The other prediction becomes a False Positive!
    assert result["metrics"]["fn"] == 0
    assert len(result["matches"]) == 1
    assert len(result["false_positives"]) == 1


def test_matching_rejects_obviously_unrelated_category():
    # Security defect vs style prediction on the same line
    gt = [_make_gt(id_="GT-001", category="security", line=4, desc="Hardcoded password")]
    pred = [_make_pred(tool="ruff", category="quality_style", line=4, code="E501", message="Line too long")]

    result = match_predictions_with_ground_truth(pred, gt)
    assert result["metrics"]["tp"] == 0
    assert result["metrics"]["fp"] == 1
    assert result["metrics"]["fn"] == 1
    assert len(result["matches"]) == 0


def test_matching_rejects_distant_lines():
    # Same category and similar description, but lines are far apart (line 4 vs line 20)
    gt = [_make_gt(id_="GT-001", category="security", line=4, desc="Hardcoded password")]
    pred = [_make_pred(tool="bandit", category="security", line=20, message="Hardcoded password")]

    result = match_predictions_with_ground_truth(pred, gt)
    assert result["metrics"]["tp"] == 0
    assert result["metrics"]["fp"] == 1
    assert result["metrics"]["fn"] == 1


# ============================================================
# END-TO-END PIPELINE EVALUATION (OFFLINE MOCK ONLY)
# ============================================================

def test_evaluate_file_static_mode_bad_code():
    eval_res = evaluate_file("samples/bad_code.py", mode="static")
    assert eval_res["mode"] == "static"
    m = eval_res["metrics"]
    assert m["tp"] >= 1
    assert m["fp"] >= 0
    assert 0.0 <= m["precision"] <= 1.0
    assert 0.0 <= m["recall"] <= 1.0


def test_evaluate_file_llm_mode_mock_bad_code():
    eval_res = evaluate_file("samples/bad_code.py", mode="llm", provider="mock")
    assert eval_res["mode"] == "llm"
    m = eval_res["metrics"]
    assert m["tp"] >= 1
    assert m["fp"] >= 0


def test_evaluate_file_hybrid_mode_mock_bad_code():
    eval_res = evaluate_file("samples/bad_code.py", mode="hybrid", provider="mock")
    assert eval_res["mode"] == "hybrid"
    m = eval_res["metrics"]
    assert m["tp"] >= 1
    assert m["fp"] >= 0


def test_compare_modes_for_file_offline():
    comp = compare_modes_for_file("samples/bad_code.py", provider="mock")
    assert "static" in comp["results"]
    assert "llm" in comp["results"]
    assert "hybrid" in comp["results"]
    assert comp["ground_truth_count"] >= 3


def test_evaluate_dataset_offline():
    report = evaluate_dataset(provider="mock")
    assert report["files_evaluated"] >= 1
    assert "aggregate" in report
    assert "static" in report["aggregate"]
    assert "llm" in report["aggregate"]
    assert "hybrid" in report["aggregate"]
    for mode in ("static", "llm", "hybrid"):
        agg_m = report["aggregate"][mode]
        assert "tp" in agg_m
        assert "fp" in agg_m
        assert "fn" in agg_m
        assert "precision" in agg_m
        assert "recall" in agg_m
        assert "f1" in agg_m
        assert set(agg_m["category_metrics"]) == {
            "security",
            "quality_style",
            "maintainability",
            "complexity",
            "performance",
        }
        assert "tp" in agg_m["category_metrics"]["security"]
