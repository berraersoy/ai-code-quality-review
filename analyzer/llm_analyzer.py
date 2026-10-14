import json
from pathlib import Path


VALID_CATEGORIES = {
    "security",
    "quality_style",
    "performance",
    "maintainability"
}

VALID_SEVERITIES = {
    "low",
    "medium",
    "high"
}


def read_source_code(file_path):
    """Read Python source code from a file."""

    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def build_review_prompt(source_code):
    """
    Build the prompt that will later be sent to a real LLM.

    The LLM is expected to analyze the code independently
    from the static-analysis tools.
    """

    return f"""
You are a code quality reviewer.

Analyze the following Python source code.

Look for:
- security problems
- maintainability problems
- performance problems
- code quality and style problems

For every issue return:

- category
- code
- line
- severity
- message
- explanation
- suggested_fix

Allowed categories:
security
quality_style
performance
maintainability

Allowed severity values:
low
medium
high

Return structured JSON only.

SOURCE CODE:

{source_code}
""".strip()


def run_mock_llm(file_path, source_code):
    """
    Temporary mock LLM provider.

    This simulates structured findings until
    a real LLM API is connected.
    """

    findings = []

    lines = source_code.splitlines()

    # Simulate detection of a hardcoded password
    for line_number, line in enumerate(lines, start=1):
        if "password" in line.lower() and "=" in line:

            findings.append({
                "tool": "llm",
                "category": "security",
                "code": "LLM-SEC-001",
                "line": line_number,
                "severity": "medium",
                "message": (
                    "A password appears to be hardcoded "
                    "in the source code."
                ),
                "explanation": (
                    "Hardcoded credentials can expose sensitive "
                    "information if the source code is shared "
                    "or stored in version control."
                ),
                "suggested_fix": (
                    "Store the password in an environment variable "
                    "or a secure secret-management system."
                )
            })

    # Keep the original prototype behavior for bad_code.py.
    # Later this section will be replaced by a real LLM response.
    if Path(file_path).name == "bad_code.py":

        findings.append({
            "tool": "llm",
            "category": "maintainability",
            "code": "LLM-MNT-001",
            "line": 9,
            "severity": "low",
            "message": (
                "The function contains deeply nested "
                "conditional logic."
            ),
            "explanation": (
                "Nested conditions can make code harder "
                "to read and maintain."
            ),
            "suggested_fix": (
                "Combine related conditions or simplify "
                "the control flow."
            )
        })

    return findings


def validate_finding(finding):
    """
    Validate one LLM finding before allowing it
    into the hybrid-analysis pipeline.
    """

    required_fields = {
        "tool",
        "category",
        "code",
        "line",
        "severity",
        "message",
        "explanation",
        "suggested_fix"
    }

    if not required_fields.issubset(finding.keys()):
        return False

    if finding["category"] not in VALID_CATEGORIES:
        return False

    if finding["severity"] not in VALID_SEVERITIES:
        return False

    if not isinstance(finding["line"], int):
        return False

    if finding["line"] < 1:
        return False

    return True


def validate_findings(findings):
    """Remove malformed LLM findings."""

    return [
        finding
        for finding in findings
        if validate_finding(finding)
    ]


def analyze_with_llm(file_path, provider="mock"):
    """
    Main LLM-analysis entry point.

    provider='mock' is used for now.
    A real API provider will be added later.
    """

    source_code = read_source_code(file_path)

    # We build this already because the same prompt structure
    # will later be sent to the real LLM.
    prompt = build_review_prompt(source_code)

    if provider == "mock":
        raw_findings = run_mock_llm(
            file_path,
            source_code
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}"
        )

    findings = validate_findings(raw_findings)

    return {
        "file": file_path,
        "analysis_mode": "llm_only",
        "provider": provider,
        "prompt_created": bool(prompt),
        "total_llm_findings": len(findings),
        "findings": findings
    }


def save_llm_report(report, output_file="llm_report.json"):
    """Save LLM analysis as JSON."""

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False
        )


if __name__ == "__main__":

    file_path = "samples/bad_code.py"

    report = analyze_with_llm(file_path)

    save_llm_report(report)

    print(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False
        )
    )