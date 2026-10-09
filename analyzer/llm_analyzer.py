import json


def analyze_with_llm(file_path):
    """
    Temporary mock LLM analyzer.

    This simulates the structured output that will later
    come from a real Large Language Model API.
    """

    with open(file_path, "r", encoding="utf-8") as file:
        source_code = file.read()

    # Later this section will be replaced by a real LLM API call.
    mock_findings = [
        {
            "tool": "llm",
            "category": "security",
            "code": "LLM-SEC-001",
            "line": 4,
            "severity": "medium",
            "message": "A password appears to be hardcoded in the source code.",
            "explanation": (
                "Hardcoded credentials can expose sensitive information "
                "if the source code is shared or stored in version control."
            ),
            "suggested_fix": (
                "Store the password in an environment variable or "
                "a secure secret-management system."
            )
        },
        {
            "tool": "llm",
            "category": "maintainability",
            "code": "LLM-MNT-001",
            "line": 9,
            "severity": "low",
            "message": "The function contains deeply nested conditional logic.",
            "explanation": (
                "Nested conditions can make code harder to read "
                "and maintain."
            ),
            "suggested_fix": (
                "Combine related conditions or simplify the control flow."
            )
        }
    ]

    return {
        "file": file_path,
        "analysis_mode": "mock_llm",
        "source_length": len(source_code),
        "total_llm_findings": len(mock_findings),
        "findings": mock_findings
    }


def save_llm_report(report, output_file="llm_report.json"):
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"LLM report saved to: {output_file}")


if __name__ == "__main__":
    report = analyze_with_llm("samples/bad_code.py")

    save_llm_report(report)

    print(json.dumps(report, indent=4))