import json
from difflib import SequenceMatcher

from analyzer.static_analyzer import analyze_file
from analyzer.llm_analyzer import analyze_with_llm


# ============================================================
# MATCHING CONFIGURATION
# ============================================================

MATCH_THRESHOLD = 0.55
MIN_MESSAGE_SIMILARITY = 0.20

CATEGORY_WEIGHT = 0.35
LINE_WEIGHT = 0.30
MESSAGE_WEIGHT = 0.35


# ============================================================
# CATEGORY NORMALIZATION
# ============================================================

CATEGORY_GROUPS = {
    "security": {
        "security"
    },

    "maintainability": {
        "maintainability",
        "quality_style",
        "style",
        "quality"
    },

    "complexity": {
        "complexity"
    },

    "performance": {
        "performance"
    }
}


def normalize_category(category):
    """
    Convert different category names into a common category.
    """

    if not category:
        return "unknown"

    category = category.lower().strip()

    for normalized_category, aliases in CATEGORY_GROUPS.items():

        if category in aliases:
            return normalized_category

    return category


# ============================================================
# CATEGORY SIMILARITY
# ============================================================

def calculate_category_similarity(
    static_category,
    llm_category
):
    """
    Compare normalized categories.

    Returns:
        1.0 -> same normalized category
        0.5 -> related category
        0.0 -> unrelated category
    """

    static_normalized = normalize_category(
        static_category
    )

    llm_normalized = normalize_category(
        llm_category
    )

    if static_normalized == llm_normalized:
        return 1.0

    related_pairs = {
        ("maintainability", "complexity"),
        ("complexity", "maintainability")
    }

    if (
        static_normalized,
        llm_normalized
    ) in related_pairs:
        return 0.5

    return 0.0


# ============================================================
# LINE SIMILARITY
# ============================================================

def calculate_line_similarity(
    static_line,
    llm_line
):
    """
    Compare source-code locations.

    Same line     -> 1.0
    1 line apart  -> 0.8
    2 lines apart -> 0.6
    3 lines apart -> 0.4
    farther       -> 0.0
    """

    if static_line is None or llm_line is None:
        return 0.0

    try:
        difference = abs(
            int(static_line) - int(llm_line)
        )

    except (TypeError, ValueError):
        return 0.0

    if difference == 0:
        return 1.0

    if difference == 1:
        return 0.8

    if difference == 2:
        return 0.6

    if difference == 3:
        return 0.4

    return 0.0


# ============================================================
# MESSAGE SIMILARITY
# ============================================================

def normalize_text(text):
    """
    Normalize text before comparison.
    """

    if not text:
        return ""

    return str(text).lower().strip()


def calculate_message_similarity(
    static_message,
    llm_message
):
    """
    Calculate textual similarity between two issue messages.
    """

    static_text = normalize_text(
        static_message
    )

    llm_text = normalize_text(
        llm_message
    )

    if not static_text or not llm_text:
        return 0.0

    return SequenceMatcher(
        None,
        static_text,
        llm_text
    ).ratio()


# ============================================================
# MATCH SCORE
# ============================================================

def calculate_match_score(
    static_finding,
    llm_finding
):
    """
    Calculate the weighted similarity score between
    a static-analysis finding and an LLM finding.
    """

    category_similarity = (
        calculate_category_similarity(
            static_finding.get("category"),
            llm_finding.get("category")
        )
    )

    line_similarity = (
        calculate_line_similarity(
            static_finding.get("line"),
            llm_finding.get("line")
        )
    )

    message_similarity = (
        calculate_message_similarity(
            static_finding.get("message"),
            llm_finding.get("message")
        )
    )

    score = (
        category_similarity * CATEGORY_WEIGHT
        + line_similarity * LINE_WEIGHT
        + message_similarity * MESSAGE_WEIGHT
    )

    details = {
        "category_similarity": round(
            category_similarity,
            3
        ),

        "line_similarity": round(
            line_similarity,
            3
        ),

        "message_similarity": round(
            message_similarity,
            3
        )
    }

    return round(score, 3), details


# ============================================================
# MATCH VALIDATION
# ============================================================

def is_valid_match(
    score,
    match_details
):
    """
    Decide whether a possible match should be accepted.

    A high weighted score alone is not enough.

    The textual descriptions must also have a minimum
    similarity. This reduces false hybrid confirmations.
    """

    if score < MATCH_THRESHOLD:
        return False

    message_similarity = match_details.get(
        "message_similarity",
        0.0
    )

    if (
        message_similarity
        < MIN_MESSAGE_SIMILARITY
    ):
        return False

    return True


# ============================================================
# SEVERITY NORMALIZATION
# ============================================================

def normalize_severity(severity):
    """
    Normalize severity labels from different analyzers.
    """

    if not severity:
        return "low"

    severity = str(
        severity
    ).lower()

    mapping = {
        "warning": "low",
        "info": "low",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "critical": "high"
    }

    return mapping.get(
        severity,
        "low"
    )


def severity_rank(severity):
    """
    Convert severity into numeric ranking.
    """

    severity = normalize_severity(
        severity
    )

    ranks = {
        "low": 1,
        "medium": 2,
        "high": 3
    }

    return ranks.get(
        severity,
        1
    )


def merge_severity(
    static_severity,
    llm_severity
):
    """
    Use the higher severity when two analyzers
    confirm the same issue.
    """

    static_normalized = normalize_severity(
        static_severity
    )

    llm_normalized = normalize_severity(
        llm_severity
    )

    if (
        severity_rank(llm_normalized)
        > severity_rank(static_normalized)
    ):
        return llm_normalized

    return static_normalized


# ============================================================
# CREATE HYBRID FINDING
# ============================================================

def create_hybrid_finding(
    static_finding,
    llm_finding,
    match_score,
    match_details
):
    """
    Merge matching static and LLM findings.
    """

    final_category = normalize_category(
        llm_finding.get(
            "category",
            static_finding.get("category")
        )
    )

    final_severity = merge_severity(
        static_finding.get("severity"),
        llm_finding.get("severity")
    )

    return {
        "source": "hybrid",

        "category": final_category,

        "line": static_finding.get(
            "line"
        ),

        "severity": final_severity,

        "static_tool": static_finding.get(
            "tool"
        ),

        "static_code": static_finding.get(
            "code"
        ),

        "llm_code": llm_finding.get(
            "code"
        ),

        "message": static_finding.get(
            "message"
        ),

        "llm_explanation": llm_finding.get(
            "explanation"
        ),

        "suggested_fix": llm_finding.get(
            "suggested_fix"
        ),

        "confirmed_by": [
            static_finding.get("tool"),
            "llm"
        ],

        "match_score": match_score,

        "match_details": match_details
    }


# ============================================================
# UNMATCHED FINDINGS
# ============================================================

def create_static_finding(finding):
    """
    Create an unmatched static-only finding.
    """

    result = finding.copy()

    result["source"] = "static"

    return result


def create_llm_finding(finding):
    """
    Create an unmatched LLM-only finding.
    """

    result = finding.copy()

    result["source"] = "llm"

    return result


# ============================================================
# FIND BEST VALID LLM MATCH
# ============================================================

def find_best_llm_match(
    static_finding,
    llm_findings,
    used_llm_indexes
):
    """
    Find the strongest VALID LLM match for one
    static-analysis finding.

    Invalid candidates are ignored even if their
    weighted score is relatively high.
    """

    best_index = None
    best_score = 0.0
    best_details = None

    for index, llm_finding in enumerate(
        llm_findings
    ):

        if index in used_llm_indexes:
            continue

        score, details = calculate_match_score(
            static_finding,
            llm_finding
        )

        if not is_valid_match(
            score,
            details
        ):
            continue

        if score > best_score:

            best_index = index
            best_score = score
            best_details = details

    return (
        best_index,
        best_score,
        best_details
    )


# ============================================================
# HYBRID ANALYSIS ENGINE
# ============================================================

def run_hybrid_analysis(file_path):
    """
    Run static analysis and LLM analysis,
    then intelligently merge matching findings.
    """

    # --------------------------------------------------------
    # STATIC ANALYSIS
    # --------------------------------------------------------

    static_report = analyze_file(
        file_path
    )

    static_findings = static_report.get(
        "findings",
        []
    )

    # --------------------------------------------------------
    # LLM ANALYSIS
    # --------------------------------------------------------

    llm_report = analyze_with_llm(
        file_path
    )

    llm_findings = llm_report.get(
        "findings",
        []
    )

    # --------------------------------------------------------
    # MATCHING
    # --------------------------------------------------------

    final_findings = []

    used_llm_indexes = set()

    hybrid_confirmed = 0

    for static_finding in static_findings:

        (
            best_index,
            best_score,
            best_details
        ) = find_best_llm_match(
            static_finding,
            llm_findings,
            used_llm_indexes
        )

        # ----------------------------------------------------
        # HYBRID MATCH
        # ----------------------------------------------------

        if best_index is not None:

            llm_finding = llm_findings[
                best_index
            ]

            hybrid_finding = (
                create_hybrid_finding(
                    static_finding,
                    llm_finding,
                    best_score,
                    best_details
                )
            )

            final_findings.append(
                hybrid_finding
            )

            used_llm_indexes.add(
                best_index
            )

            hybrid_confirmed += 1

        # ----------------------------------------------------
        # STATIC-ONLY FINDING
        # ----------------------------------------------------

        else:

            final_findings.append(
                create_static_finding(
                    static_finding
                )
            )

    # --------------------------------------------------------
    # UNMATCHED LLM FINDINGS
    # --------------------------------------------------------

    for index, llm_finding in enumerate(
        llm_findings
    ):

        if index not in used_llm_indexes:

            final_findings.append(
                create_llm_finding(
                    llm_finding
                )
            )

    # --------------------------------------------------------
    # FINAL REPORT
    # --------------------------------------------------------

    report = {
        "file": file_path,

        "analysis_mode": "hybrid",

        "summary": {
            "static_raw_findings": len(
                static_findings
            ),

            "llm_raw_findings": len(
                llm_findings
            ),

            "hybrid_confirmed": (
                hybrid_confirmed
            ),

            "unique_findings": len(
                final_findings
            )
        },

        # Structural information
        "ast_analysis": static_report.get(
            "ast_analysis"
        ),

        # Measurements such as cyclomatic complexity
        "metrics": static_report.get(
            "metrics",
            {}
        ),

        # Actual issues
        "findings": final_findings
    }

    return report


# ============================================================
# SAVE REPORT
# ============================================================

def save_hybrid_report(
    report,
    output_file="hybrid_report.json"
):
    """
    Save hybrid report as JSON.
    """

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
        f"\nHybrid report saved to: {output_file}"
    )


# ============================================================
# TERMINAL SUMMARY
# ============================================================

def print_hybrid_summary(report):
    """
    Print hybrid-analysis summary.
    """

    summary = report.get(
        "summary",
        {}
    )

    print("\n" + "=" * 60)
    print("HYBRID CODE QUALITY REVIEW")
    print("=" * 60)

    print(
        f"\nFile: {report.get('file')}"
    )

    print(
        f"Static raw findings: "
        f"{summary.get('static_raw_findings', 0)}"
    )

    print(
        f"LLM raw findings: "
        f"{summary.get('llm_raw_findings', 0)}"
    )

    print(
        f"Hybrid confirmed: "
        f"{summary.get('hybrid_confirmed', 0)}"
    )

    print(
        f"Unique findings: "
        f"{summary.get('unique_findings', 0)}"
    )

    print("\nCOMPLEXITY METRICS")
    print("-" * 60)

    complexity_metrics = (
        report
        .get("metrics", {})
        .get("complexity", [])
    )

    if not complexity_metrics:

        print(
            "No complexity metrics found."
        )

    else:

        for metric in complexity_metrics:

            print(
                f"{metric.get('function')} "
                f"| Line {metric.get('line')} "
                f"| CC: {metric.get('complexity')} "
                f"| Rank: {metric.get('rank')}"
            )

    print("\n" + "=" * 60)


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    file_path = "samples/bad_code.py"

    report = run_hybrid_analysis(
        file_path
    )

    print_hybrid_summary(
        report
    )

    save_hybrid_report(
        report
    )