from analyzer.hybrid_analyzer import run_hybrid_analysis


def get_finding_by_static_code(
    report,
    code
):

    for finding in report[
        "findings"
    ]:

        if finding.get(
            "code"
        ) == code:

            return finding

        if finding.get(
            "static_code"
        ) == code:

            return finding

    return None


def test_bad_code_summary():

    report = run_hybrid_analysis(
        "samples/bad_code.py"
    )

    summary = report[
        "summary"
    ]

    assert (
        summary[
            "static_raw_findings"
        ]
        == 6
    )

    assert (
        summary[
            "llm_raw_findings"
        ]
        == 2
    )

    assert (
        summary[
            "hybrid_confirmed"
        ]
        == 2
    )

    assert (
        summary[
            "unique_findings"
        ]
        == 6
    )


def test_unused_variable_remains_static():

    report = run_hybrid_analysis(
        "samples/bad_code.py"
    )

    finding = (
        get_finding_by_static_code(
            report,
            "F841"
        )
    )

    assert finding is not None

    assert (
        finding["source"]
        == "static"
    )

    assert finding["line"] == 7


def test_nested_condition_is_hybrid():

    report = run_hybrid_analysis(
        "samples/bad_code.py"
    )

    findings = [
        finding
        for finding
        in report["findings"]

        if finding.get(
            "static_code"
        ) == "SIM102"

        and finding.get(
            "source"
        ) == "hybrid"
    ]

    assert len(findings) == 1

    finding = findings[0]

    assert (
        finding["llm_code"]
        == "LLM-MNT-001"
    )

    assert finding["line"] == 9

    assert (
        "ruff"
        in finding["confirmed_by"]
    )

    assert (
        "llm"
        in finding["confirmed_by"]
    )


def test_hardcoded_password_is_hybrid():

    report = run_hybrid_analysis(
        "samples/bad_code.py"
    )

    finding = (
        get_finding_by_static_code(
            report,
            "B105"
        )
    )

    assert finding is not None

    assert (
        finding["source"]
        == "hybrid"
    )

    assert (
        finding["static_tool"]
        == "bandit"
    )

    assert (
        finding["llm_code"]
        == "LLM-SEC-001"
    )

    assert finding["line"] == 4


def test_llm_finding_is_not_used_twice():

    report = run_hybrid_analysis(
        "samples/bad_code.py"
    )

    llm_codes = [
        finding.get(
            "llm_code"
        )

        for finding
        in report["findings"]

        if finding.get(
            "source"
        ) == "hybrid"
    ]

    assert (
        llm_codes.count(
            "LLM-MNT-001"
        )
        == 1
    )

    assert (
        llm_codes.count(
            "LLM-SEC-001"
        )
        == 1
    )


def test_low_complexity_is_metric_not_finding():

    report = run_hybrid_analysis(
        "samples/bad_code.py"
    )

    complexity = (
        report["metrics"][
            "complexity"
        ]
    )

    assert len(complexity) == 1

    metric = complexity[0]

    assert (
        metric["function"]
        == "calculate"
    )

    assert metric["line"] == 6

    assert (
        metric["complexity"]
        == 4
    )

    assert metric["rank"] == "A"

    radon_findings = [
        finding
        for finding
        in report["findings"]

        if finding.get(
            "tool"
        ) == "radon"
    ]

    assert len(
        radon_findings
    ) == 0


def test_cleaner_sample_has_no_llm_or_hybrid_findings():

    report = run_hybrid_analysis(
        "samples/test_code.py"
    )

    summary = report[
        "summary"
    ]

    assert (
        summary[
            "llm_raw_findings"
        ]
        == 0
    )

    assert (
        summary[
            "hybrid_confirmed"
        ]
        == 0
    )