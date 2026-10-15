import pytest
from unittest.mock import MagicMock, patch

from analyzer.llm_analyzer import (
    analyze_with_llm,
    build_review_prompt,
    is_temporary_error,
    run_gemini_llm,
    validate_finding,
    validate_findings,
)


def _make_valid_finding(**overrides):
    base = {
        "tool": "llm",
        "category": "security",
        "code": "LLM-SEC-001",
        "line": 4,
        "severity": "medium",
        "message": "A password appears to be hardcoded.",
        "explanation": "Hardcoded credentials can expose sensitive info.",
        "suggested_fix": "Store in environment variable."
    }
    base.update(overrides)
    return base


# ============================================================
# VALIDATION TESTS
# ============================================================

def test_validate_finding_accepts_valid():
    finding = _make_valid_finding()
    assert validate_finding(finding, total_lines=14) is True


def test_validate_finding_rejects_missing_field():
    finding = _make_valid_finding()
    del finding["suggested_fix"]
    assert validate_finding(finding, total_lines=14) is False


def test_validate_finding_rejects_invalid_category():
    finding = _make_valid_finding(category="unknown_category")
    assert validate_finding(finding, total_lines=14) is False


def test_validate_finding_accepts_complexity_category():
    finding = _make_valid_finding(
        category="complexity",
        code="LLM-COMPLEXITY-001",
        message="The function has many independent branches.",
        explanation="The nested conditions create multiple control-flow paths.",
        suggested_fix="Extract the branches into smaller decision-focused helpers.",
    )
    assert validate_finding(finding, total_lines=14) is True
    assert finding["category"] == "complexity"


@pytest.mark.parametrize(
    "category",
    ["security", "quality_style", "maintainability", "performance"],
)
def test_validate_finding_keeps_existing_categories(category):
    finding = _make_valid_finding(category=category)
    assert validate_finding(finding, total_lines=14) is True


def test_complexity_prompt_requires_measurable_control_flow_evidence():
    prompt = build_review_prompt("def example():\n    return 1")
    assert "complexity" in prompt.lower()
    assert "measurably high" in prompt
    assert "subjective style preferences" in prompt


def test_validate_finding_rejects_invalid_severity():
    finding = _make_valid_finding(severity="critical")
    assert validate_finding(finding, total_lines=14) is False


def test_validate_finding_rejects_zero_or_negative_line():
    assert validate_finding(_make_valid_finding(line=0), total_lines=14) is False
    assert validate_finding(_make_valid_finding(line=-5), total_lines=14) is False


def test_validate_finding_rejects_impossible_line_number():
    finding = _make_valid_finding(line=999)
    assert validate_finding(finding, total_lines=14) is False


def test_validate_finding_rejects_non_integer_line():
    assert validate_finding(_make_valid_finding(line=True), total_lines=14) is False
    assert validate_finding(_make_valid_finding(line="abc"), total_lines=14) is False


def test_validate_finding_normalizes_case_and_string_line():
    finding = _make_valid_finding(
        category="SECURITY",
        severity="HIGH",
        line="10"
    )
    assert validate_finding(finding, total_lines=14) is True
    assert finding["category"] == "security"
    assert finding["severity"] == "high"
    assert finding["line"] == 10


def test_validate_findings_filters_malformed():
    raw = [
        _make_valid_finding(line=1),
        {"invalid": "structure"},
        _make_valid_finding(line=999),  # impossible line
        _make_valid_finding(line=2, category="not_a_category"),
    ]
    valid = validate_findings(raw, total_lines=10)
    assert len(valid) == 1
    assert valid[0]["line"] == 1


# ============================================================
# ERROR CLASSIFICATION TESTS
# ============================================================

def test_is_temporary_error_detects_503_and_429():
    class DummyError(Exception):
        pass

    err_503 = DummyError("503 Service Unavailable: high demand")
    err_503.status_code = 503
    assert is_temporary_error(err_503) is True

    err_429 = DummyError("Resource exhausted")
    err_429.status_code = 429
    assert is_temporary_error(err_429) is True

    err_msg = DummyError("The model is currently experiencing high demand.")
    assert is_temporary_error(err_msg) is True


def test_is_temporary_error_rejects_permanent_errors():
    class DummyError(Exception):
        pass

    err_401 = DummyError("Invalid API key")
    err_401.status_code = 401
    assert is_temporary_error(err_401) is False

    err_400 = DummyError("Bad request")
    err_400.status_code = 400
    assert is_temporary_error(err_400) is False

    err_404 = DummyError("Model not found")
    err_404.status_code = 404
    assert is_temporary_error(err_404) is False


# ============================================================
# RETRY & BACKOFF TESTS (MOCKED - NEVER CONTACTS NETWORK)
# ============================================================

def test_gemini_retry_succeeds_after_transient_error():
    mock_client = MagicMock()

    class Transient503(Exception):
        status_code = 503

    valid_response = MagicMock()
    valid_response.choices = [
        MagicMock(message=MagicMock(content='{"findings": []}'))
    ]

    # First call raises 503, second call succeeds
    mock_client.chat.completions.create.side_effect = [
        Transient503("503 UNAVAILABLE: high demand"),
        valid_response
    ]

    with patch("analyzer.llm_analyzer.create_gemini_client", return_value=mock_client):
        findings = run_gemini_llm("test prompt", backoff_delays=[0.001])
        assert findings == []
        assert mock_client.chat.completions.create.call_count == 2


def test_gemini_retry_exhausted_raises_clean_error():
    mock_client = MagicMock()

    class Transient503(Exception):
        status_code = 503

    mock_client.chat.completions.create.side_effect = Transient503(
        "503 Service Unavailable"
    )

    with patch("analyzer.llm_analyzer.create_gemini_client", return_value=mock_client):
        with pytest.raises(RuntimeError) as exc_info:
            run_gemini_llm("test prompt", backoff_delays=[0.001, 0.001])

        assert "failed after 2 retries" in str(exc_info.value)
        assert mock_client.chat.completions.create.call_count == 3


def test_gemini_permanent_error_does_not_retry():
    mock_client = MagicMock()

    class AuthError(Exception):
        status_code = 401

    mock_client.chat.completions.create.side_effect = AuthError(
        "Invalid API Key"
    )

    with patch("analyzer.llm_analyzer.create_gemini_client", return_value=mock_client):
        with pytest.raises(RuntimeError) as exc_info:
            run_gemini_llm("test prompt", backoff_delays=[0.001, 0.001])

        assert "permanent error" in str(exc_info.value)
        # Must fail on the very first attempt without retrying
        assert mock_client.chat.completions.create.call_count == 1


# ============================================================
# DETERMINISTIC MOCK PROVIDER
# ============================================================

def test_mock_provider_is_deterministic_and_offline():
    report1 = analyze_with_llm("samples/bad_code.py", provider="mock")
    report2 = analyze_with_llm("samples/bad_code.py", provider="mock")
    assert report1 == report2
    assert report1["total_llm_findings"] == 2
