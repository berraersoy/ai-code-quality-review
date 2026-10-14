import json
import subprocess

from analyzer.ast_analyzer import analyze_ast


# ============================================================
# RUFF ANALYSIS
# ============================================================

def run_ruff(file_path):
    """
    Run Ruff on the given Python file.

    Ruff is used for:
    - code quality
    - style problems
    - unused imports
    - unused variables
    - simplification suggestions
    """

    result = subprocess.run(
        [
            "ruff",
            "check",
            file_path,
            "--output-format",
            "json"
        ],
        capture_output=True,
        text=True
    )

    if not result.stdout:
        return []

    try:
        raw_results = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    findings = []

    for issue in raw_results:

        finding = {
            "tool": "ruff",
            "category": "quality_style",
            "code": issue.get("code"),
            "line": issue.get(
                "location",
                {}
            ).get("row"),
            "severity": "warning",
            "message": issue.get("message")
        }

        findings.append(finding)

    return findings


# ============================================================
# BANDIT ANALYSIS
# ============================================================

def run_bandit(file_path):
    """
    Run Bandit security analysis.

    Bandit detects security-related problems such as:
    - hardcoded passwords
    - insecure function usage
    - dangerous subprocess usage
    - weak cryptographic practices
    """

    result = subprocess.run(
        [
            "bandit",
            "-f",
            "json",
            file_path
        ],
        capture_output=True,
        text=True
    )

    if not result.stdout:
        return []

    try:
        raw_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    raw_results = raw_data.get("results", [])

    findings = []

    for issue in raw_results:

        severity = issue.get(
            "issue_severity",
            "LOW"
        ).lower()

        finding = {
            "tool": "bandit",
            "category": "security",
            "code": issue.get("test_id"),
            "line": issue.get("line_number"),
            "severity": severity,
            "message": issue.get("issue_text")
        }

        findings.append(finding)

    return findings


# ============================================================
# RADON COMPLEXITY METRICS
# ============================================================

def run_radon(file_path):
    """
    Run Radon cyclomatic complexity analysis.

    IMPORTANT:
    Radon results are treated primarily as METRICS.

    A function with low complexity is not automatically
    considered a code-quality problem.

    Only functions above the complexity threshold will later
    be converted into findings.
    """

    result = subprocess.run(
        [
            "radon",
            "cc",
            file_path,
            "-j"
        ],
        capture_output=True,
        text=True
    )

    if not result.stdout:
        return []

    try:
        raw_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    metrics = []

    for filename, blocks in raw_data.items():

        for block in blocks:

            metric = {
                "function": block.get("name"),
                "line": block.get("lineno"),
                "complexity": block.get("complexity"),
                "rank": block.get("rank")
            }

            metrics.append(metric)

    return metrics


# ============================================================
# COMPLEXITY FINDINGS
# ============================================================

def complexity_severity(complexity):
    """
    Convert cyclomatic complexity into severity.

    Complexity:
        1-5   -> acceptable
        6-10  -> low
        11-20 -> medium
        21+   -> high
    """

    if complexity <= 5:
        return None

    if complexity <= 10:
        return "low"

    if complexity <= 20:
        return "medium"

    return "high"


def create_complexity_findings(complexity_metrics):
    """
    Convert only sufficiently complex functions into findings.

    Complexity <= 5 is stored only as a metric.
    """

    findings = []

    for metric in complexity_metrics:

        complexity = metric.get(
            "complexity",
            0
        )

        severity = complexity_severity(
            complexity
        )

        # Acceptable complexity -> metric only
        if severity is None:
            continue

        finding = {
            "tool": "radon",
            "category": "complexity",
            "code": "CC",
            "line": metric.get("line"),
            "severity": severity,
            "message": (
                f"{metric.get('function')} has cyclomatic "
                f"complexity {complexity} "
                f"(Rank {metric.get('rank')})"
            )
        }

        findings.append(finding)

    return findings


# ============================================================
# STATIC ANALYSIS ENGINE
# ============================================================

def analyze_file(file_path):
    """
    Main static-analysis pipeline.

    Pipeline:
        Python file
            |
            +-- AST
            |
            +-- Ruff
            |
            +-- Bandit
            |
            +-- Radon metrics
                    |
                    +-- high-enough complexity -> finding
    """

    # --------------------------------------------------------
    # AST STRUCTURAL ANALYSIS
    # --------------------------------------------------------

    ast_analysis = analyze_ast(
        file_path
    )

    # --------------------------------------------------------
    # STATIC ANALYSIS TOOLS
    # --------------------------------------------------------

    ruff_findings = run_ruff(
        file_path
    )

    bandit_findings = run_bandit(
        file_path
    )

    complexity_metrics = run_radon(
        file_path
    )

    complexity_findings = create_complexity_findings(
        complexity_metrics
    )

    # --------------------------------------------------------
    # COMBINE FINDINGS
    # --------------------------------------------------------

    findings = []

    findings.extend(
        ruff_findings
    )

    findings.extend(
        bandit_findings
    )

    findings.extend(
        complexity_findings
    )

    # --------------------------------------------------------
    # FINAL STATIC REPORT
    # --------------------------------------------------------

    report = {
        "file": file_path,
        "analysis_mode": "static",
        "total_issues": len(findings),

        "ast_analysis": ast_analysis,

        "metrics": {
            "complexity": complexity_metrics
        },

        "findings": findings
    }

    return report


# ============================================================
# TERMINAL REPORT
# ============================================================

def print_report(report):

    print("\n" + "=" * 60)

    print(
        "STATIC CODE QUALITY ANALYSIS"
    )

    print("=" * 60)

    print(
        f"\nFile: {report['file']}"
    )

    print(
        f"Total findings: {report['total_issues']}"
    )

    # --------------------------------------------------------
    # FINDINGS
    # --------------------------------------------------------

    print("\nFINDINGS")
    print("-" * 60)

    if not report["findings"]:
        print(
            "No static-analysis issues found."
        )

    else:

        for finding in report["findings"]:

            print(
                f"[{finding['tool'].upper()}] "
                f"{finding['code']} "
                f"| Line {finding['line']} "
                f"| Severity: {finding['severity']}"
            )

            print(
                f"  {finding['message']}"
            )

    # --------------------------------------------------------
    # COMPLEXITY METRICS
    # --------------------------------------------------------

    print("\nCOMPLEXITY METRICS")
    print("-" * 60)

    complexity_metrics = report.get(
        "metrics",
        {}
    ).get(
        "complexity",
        []
    )

    if not complexity_metrics:

        print(
            "No functions found."
        )

    else:

        for metric in complexity_metrics:

            print(
                f"{metric['function']} "
                f"| Line {metric['line']} "
                f"| CC: {metric['complexity']} "
                f"| Rank: {metric['rank']}"
            )

    print("\n" + "=" * 60)


# ============================================================
# SAVE JSON REPORT
# ============================================================

def save_json_report(
    report,
    output_file="report.json"
):

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(
        f"\nStatic report saved to: {output_file}"
    )


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    file_path = "samples/bad_code.py"

    report = analyze_file(
        file_path
    )

    print_report(
        report
    )

    save_json_report(
        report
    )