from evaluation.visualize import build_visualization_html


def _category_metrics(tp=0, fp=0, fn=0, f1=0.0):
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": 0.0,
        "recall": 0.0,
        "f1": f1,
    }


def test_dashboard_uses_report_values_and_marks_missing_ground_truth():
    report = {
        "provider": "mock",
        "aggregate": {
            "static": {
                "precision": 0.731,
                "recall": 0.842,
                "f1": 0.781,
                "category_metrics": {
                    "security": _category_metrics(fn=1, f1=0.0),
                    "performance": _category_metrics(),
                },
            },
            "llm": {
                "precision": 0.5,
                "recall": 0.25,
                "f1": 0.333,
                "category_metrics": {
                    "security": _category_metrics(tp=1, f1=0.8),
                    "performance": _category_metrics(),
                },
            },
        },
    }

    dashboard = build_visualization_html(report)

    assert "MOCK RESULTS" in dashboard
    assert "not real Gemini performance results" in dashboard
    assert "0.731" in dashboard
    assert "N/A (no ground-truth examples)" in dashboard
    assert "N/A (mode unavailable)" in dashboard
    assert "0.000" in dashboard
    assert "security" in dashboard
    assert "performance" in dashboard


def test_dashboard_accepts_single_file_evaluation_report_shape():
    report = {
        "provider": "mock",
        "mode": "static",
        "metrics": {
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        },
        "category_metrics": {
            "security": _category_metrics(tp=1, f1=1.0),
        },
    }

    dashboard = build_visualization_html(report)

    assert "Static" in dashboard
    assert "1.000" in dashboard
    assert "LLM" in dashboard
    assert "Hybrid" in dashboard
    assert "N/A (mode unavailable)" in dashboard
