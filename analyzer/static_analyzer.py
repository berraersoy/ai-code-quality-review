import subprocess
import json

from analyzer.ast_analyzer import analyze_ast


# --------------------------------------------------
# RUFF
# --------------------------------------------------

def run_ruff(file_path):
    result = subprocess.run(
        ["ruff", "check", file_path, "--output-format", "json"],
        capture_output=True,
        text=True
    )

    if not result.stdout:
        return []

    raw_results = json.loads(result.stdout)
    findings = []

    for issue in raw_results:
        findings.append({
            "tool": "ruff",
            "category": "quality_style",
            "code": issue.get("code"),
            "line": issue.get("location", {}).get("row"),
            "severity": "warning",
            "message": issue.get("message")
        })

    return findings


# --------------------------------------------------
# BANDIT
# --------------------------------------------------

def run_bandit(file_path):
    result = subprocess.run(
        ["bandit", "-f", "json", file_path],
        capture_output=True,
        text=True
    )

    if not result.stdout:
        return []

    raw_data = json.loads(result.stdout)
    raw_results = raw_data.get("results", [])

    findings = []

    for issue in raw_results:
        findings.append({
            "tool": "bandit",
            "category": "security",
            "code": issue.get("test_id"),
            "line": issue.get("line_number"),
            "severity": issue.get("issue_severity"),
            "message": issue.get("issue_text")
        })

    return findings


# --------------------------------------------------
# RADON
# --------------------------------------------------

def run_radon(file_path):
    result = subprocess.run(
        ["radon", "cc", file_path, "-j"],
        capture_output=True,
        text=True
    )

    if not result.stdout:
        return []

    raw_data = json.loads(result.stdout)

    findings = []

    for filename, blocks in raw_data.items():

        for block in blocks:
            findings.append({
                "tool": "radon",
                "category": "complexity",
                "code": "CC",
                "line": block.get("lineno"),
                "severity": complexity_severity(
                    block.get("complexity", 0)
                ),
                "message": (
                    f"{block.get('name')} has cyclomatic "
                    f"complexity {block.get('complexity')} "
                    f"(Rank {block.get('rank')})"
                )
            })

    return findings


def complexity_severity(complexity):
    if complexity <= 5:
        return "low"

    if complexity <= 10:
        return "medium"

    return "high"


# --------------------------------------------------
# STATIC ANALYSIS ENGINE
# --------------------------------------------------

def analyze_file(file_path):

    findings = []

    findings.extend(run_ruff(file_path))
    findings.extend(run_bandit(file_path))
    findings.extend(run_radon(file_path))

    ast_analysis = analyze_ast(file_path)

    return {
        "file": file_path,
        "total_issues": len(findings),
        "ast_analysis": ast_analysis,
        "findings": findings
    }


# --------------------------------------------------
# TERMINAL REPORT
# --------------------------------------------------

def print_report(report):

    print("\n" + "=" * 60)
    print("AI-ASSISTED CODE QUALITY REVIEW")
    print("=" * 60)

    print(f"\nFile: {report['file']}")
    print(f"Total findings: {report['total_issues']}")

    categories = {
        "quality_style": "QUALITY / STYLE",
        "security": "SECURITY",
        "complexity": "COMPLEXITY"
    }

    for category, title in categories.items():

        print(f"\n[{title}]")

        category_findings = [
            finding
            for finding in report["findings"]
            if finding["category"] == category
        ]

        if not category_findings:
            print("No issues found.")
            continue

        for finding in category_findings:

            print(
                f"- {finding['code']} "
                f"| Line {finding['line']} "
                f"| Severity: {finding['severity']} "
                f"| {finding['message']}"
            )

    print("\n" + "=" * 60)


# --------------------------------------------------
# SAVE JSON REPORT
# --------------------------------------------------

def save_json_report(report, output_file="report.json"):

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"\nJSON report saved to: {output_file}")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

if __name__ == "__main__":

    file_path = "samples/bad_code.py"

    report = analyze_file(file_path)

    print_report(report)

    save_json_report(report)