import json

from analyzer.static_analyzer import analyze_file
from analyzer.llm_analyzer import analyze_with_llm


def normalize_severity(severity):
    """
    Convert severity values to a common format.
    """

    if severity is None:
        return "unknown"

    return str(severity).lower()


def findings_match(static_finding, llm_finding):
    """
    Decide whether a static-analysis finding and an LLM finding
    probably refer to the same underlying problem.

    Current prototype strategy:
    - same line
    - same category
    """

    same_line = (
        static_finding.get("line")
        == llm_finding.get("line")
    )

    same_category = (
        static_finding.get("category")
        == llm_finding.get("category")
    )

    return same_line and same_category


def create_hybrid_finding(static_finding, llm_finding):
    """
    Merge matching static and LLM findings.
    """

    return {
        "source": "hybrid",
        "category": static_finding.get("category"),
        "line": static_finding.get("line"),

        "severity": normalize_severity(
            llm_finding.get(
                "severity",
                static_finding.get("severity")
            )
        ),

        "static_tool": static_finding.get("tool"),
        "static_code": static_finding.get("code"),

        "message": static_finding.get("message"),

        "llm_explanation": llm_finding.get("explanation"),

        "suggested_fix": llm_finding.get("suggested_fix"),

        "confirmed_by": [
            static_finding.get("tool"),
            "llm"
        ]
    }


def merge_findings(static_findings, llm_findings):
    """
    Match static and LLM findings and create a unified list.
    """

    merged_findings = []

    matched_static = set()
    matched_llm = set()

    # Find matching problems
    for static_index, static_finding in enumerate(static_findings):

        for llm_index, llm_finding in enumerate(llm_findings):

            if findings_match(static_finding, llm_finding):

                merged_findings.append(
                    create_hybrid_finding(
                        static_finding,
                        llm_finding
                    )
                )

                matched_static.add(static_index)
                matched_llm.add(llm_index)

                break

    # Add unmatched static findings
    for index, finding in enumerate(static_findings):

        if index not in matched_static:

            merged_findings.append({
                "source": "static",
                **finding,
                "severity": normalize_severity(
                    finding.get("severity")
                )
            })

    # Add unmatched LLM findings
    for index, finding in enumerate(llm_findings):

        if index not in matched_llm:

            merged_findings.append({
                "source": "llm",
                **finding,
                "severity": normalize_severity(
                    finding.get("severity")
                )
            })

    return merged_findings


def run_hybrid_analysis(file_path):
    """
    Run static and LLM analysis and intelligently
    combine their findings.
    """

    static_report = analyze_file(file_path)
    llm_report = analyze_with_llm(file_path)

    static_findings = static_report["findings"]
    llm_findings = llm_report["findings"]

    merged_findings = merge_findings(
        static_findings,
        llm_findings
    )

    hybrid_confirmed = [
        finding
        for finding in merged_findings
        if finding.get("source") == "hybrid"
    ]

    return {
        "file": file_path,
        "analysis_mode": "hybrid",

        "summary": {
            "static_raw_findings": len(static_findings),
            "llm_raw_findings": len(llm_findings),
            "hybrid_confirmed": len(hybrid_confirmed),
            "unique_findings": len(merged_findings)
        },

        "ast_analysis": static_report["ast_analysis"],

        "findings": merged_findings
    }


def save_hybrid_report(
    report,
    output_file="hybrid_report.json"
):
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(
        f"\nHybrid report saved to: {output_file}"
    )


def print_summary(report):

    summary = report["summary"]

    print("\n" + "=" * 60)
    print("HYBRID CODE QUALITY REVIEW")
    print("=" * 60)

    print(f"\nFile: {report['file']}")

    print(
        f"Static raw findings: "
        f"{summary['static_raw_findings']}"
    )

    print(
        f"LLM raw findings: "
        f"{summary['llm_raw_findings']}"
    )

    print(
        f"Hybrid confirmed: "
        f"{summary['hybrid_confirmed']}"
    )

    print(
        f"Unique findings: "
        f"{summary['unique_findings']}"
    )

    print("\n" + "=" * 60)


if __name__ == "__main__":

    file_path = "samples/bad_code.py"

    report = run_hybrid_analysis(file_path)

    print_summary(report)

    save_hybrid_report(report)