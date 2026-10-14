import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from radon.complexity import cc_visit
from radon.complexity import cc_rank

from analyzer.ast_analyzer import analyze_ast


# ============================================================
# COMMAND EXECUTION
# ============================================================

def resolve_tool_path(tool_name):
    """
    Find the executable for tool_name.
    Searches:
    1. System PATH
    2. sys.executable directory (e.g. venv/bin or venv/Scripts)
    3. Project venv directory
    """
    # 1. System PATH
    found = shutil.which(tool_name)
    if found:
        return found

    # 2. Same directory as current Python interpreter (e.g. venv/bin)
    py_dir = Path(sys.executable).parent
    candidate = py_dir / tool_name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)

    # 3. Project venv directory relative to this file
    workspace_venv = Path(__file__).resolve().parent.parent / "venv" / "bin" / tool_name
    if workspace_venv.is_file() and os.access(workspace_venv, os.X_OK):
        return str(workspace_venv)

    return None


def run_command(command):
    """Run an external analysis tool with clear error reporting."""
    tool_name = command[0]
    tool_path = resolve_tool_path(tool_name)

    if not tool_path:
        raise RuntimeError(
            f"Required static analysis tool '{tool_name}' was not found. "
            f"Please verify it is installed in your Python environment or PATH."
        )

    resolved_command = [tool_path] + list(command[1:])

    try:
        result = subprocess.run(
            resolved_command,
            capture_output=True,
            text=True,
            check=False
        )
        return result

    except FileNotFoundError as error:
        raise RuntimeError(
            f"Required static analysis tool could not be executed: '{tool_name}'"
        ) from error


# ============================================================
# RUFF
# ============================================================

def run_ruff(file_path):
    """Run Ruff and convert its output to project findings."""

    result = run_command([
        "ruff",
        "check",
        file_path,
        "--output-format",
        "json",
        "--select",
        "F,SIM"
    ])

    if not result.stdout.strip():
        return []

    try:
        data = json.loads(result.stdout)

    except json.JSONDecodeError:
        return []

    findings = []

    for issue in data:

        location = issue.get(
            "location",
            {}
        )

        findings.append({
            "tool": "ruff",
            "category": "quality_style",
            "code": issue.get(
                "code",
                "UNKNOWN"
            ),
            "line": location.get(
                "row",
                1
            ),
            "severity": "warning",
            "message": issue.get(
                "message",
                "Ruff finding"
            )
        })

    return findings


# ============================================================
# BANDIT
# ============================================================

def run_bandit(file_path):
    """Run Bandit security analysis."""

    result = run_command([
        "bandit",
        "-f",
        "json",
        "-q",
        file_path
    ])

    if not result.stdout.strip():
        return []

    try:
        data = json.loads(result.stdout)

    except json.JSONDecodeError:
        return []

    findings = []

    for issue in data.get(
        "results",
        []
    ):

        findings.append({
            "tool": "bandit",
            "category": "security",
            "code": issue.get(
                "test_id",
                "UNKNOWN"
            ),
            "line": issue.get(
                "line_number",
                1
            ),
            "severity": issue.get(
                "issue_severity",
                "LOW"
            ).lower(),
            "message": issue.get(
                "issue_text",
                "Bandit finding"
            )
        })

    return findings


# ============================================================
# RADON
# ============================================================

def run_radon(file_path):
    """Calculate cyclomatic-complexity metrics."""

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:
        code = file.read()

    blocks = cc_visit(code)

    metrics = []

    for block in blocks:

        metrics.append({
            "function": block.name,
            "line": block.lineno,
            "complexity": block.complexity,
            "rank": cc_rank(
                block.complexity
            )
        })

    return metrics


def complexity_severity(complexity):
    """
    Convert complexity score to finding severity.

    Low complexity is kept only as a metric.
    """

    if complexity <= 5:
        return None

    if complexity <= 10:
        return "low"

    if complexity <= 20:
        return "medium"

    return "high"


def create_complexity_findings(metrics):
    """Create findings only for meaningful complexity."""

    findings = []

    for metric in metrics:

        severity = complexity_severity(
            metric["complexity"]
        )

        if severity is None:
            continue

        findings.append({
            "tool": "radon",
            "category": "complexity",
            "code": "RADON-CC",
            "line": metric["line"],
            "severity": severity,
            "message": (
                f"Function '{metric['function']}' "
                f"has cyclomatic complexity "
                f"{metric['complexity']} "
                f"(rank {metric['rank']})."
            )
        })

    return findings


# ============================================================
# COMPLETE STATIC ANALYSIS
# ============================================================

def analyze_file(file_path):
    """Run the complete static-analysis pipeline."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Source file not found: {file_path}")

    ast_analysis = analyze_ast(
        file_path
    )

    ruff_findings = run_ruff(
        file_path
    )

    bandit_findings = run_bandit(
        file_path
    )

    complexity_metrics = run_radon(
        file_path
    )

    complexity_findings = (
        create_complexity_findings(
            complexity_metrics
        )
    )

    findings = (
        ruff_findings
        + bandit_findings
        + complexity_findings
    )

    return {
        "file": file_path,
        "analysis_mode": "static",
        "total_issues": len(findings),

        "ast_analysis": ast_analysis,

        "metrics": {
            "complexity": complexity_metrics
        },

        "findings": findings
    }


if __name__ == "__main__":

    report = analyze_file(
        "samples/bad_code.py"
    )

    print(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False
        )
    )