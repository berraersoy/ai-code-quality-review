import json

from difflib import SequenceMatcher

from analyzer.static_analyzer import analyze_file
from analyzer.llm_analyzer import analyze_with_llm


MATCH_THRESHOLD = 0.55
MIN_MESSAGE_SIMILARITY = 0.20

CATEGORY_WEIGHT = 0.35
LINE_WEIGHT = 0.30
MESSAGE_WEIGHT = 0.35


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


SEVERITY_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3
}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_category(category):

    if not category:
        return ""

    category = (
        str(category)
        .strip()
        .lower()
    )

    for normalized, values in (
        CATEGORY_GROUPS.items()
    ):

        if category in values:
            return normalized

    return category


def normalize_severity(severity):

    if not severity:
        return "low"

    severity = (
        str(severity)
        .strip()
        .lower()
    )

    if severity in {
        "warning",
        "info"
    }:
        return "low"

    if severity == "critical":
        return "high"

    if severity in {
        "low",
        "medium",
        "high"
    }:
        return severity

    return "low"


# ============================================================
# SIMILARITY
# ============================================================

def category_similarity(
    static_category,
    llm_category
):

    static_normalized = (
        normalize_category(
            static_category
        )
    )

    llm_normalized = (
        normalize_category(
            llm_category
        )
    )

    if (
        static_normalized
        == llm_normalized
    ):
        return 1.0

    related = {
        frozenset({
            "maintainability",
            "complexity"
        })
    }

    pair = frozenset({
        static_normalized,
        llm_normalized
    })

    if pair in related:
        return 0.5

    return 0.0


def line_similarity(
    static_line,
    llm_line
):

    if (
        not isinstance(
            static_line,
            int
        )
        or not isinstance(
            llm_line,
            int
        )
    ):
        return 0.0

    difference = abs(
        static_line - llm_line
    )

    if difference == 0:
        return 1.0

    if difference == 1:
        return 0.8

    if difference == 2:
        return 0.6

    if difference == 3:
        return 0.4

    return 0.0


def message_similarity(
    static_message,
    llm_message
):

    if (
        not static_message
        or not llm_message
    ):
        return 0.0

    return SequenceMatcher(
        None,
        str(static_message).lower(),
        str(llm_message).lower()
    ).ratio()


# ============================================================
# MATCHING SCORE
# ============================================================

def calculate_match_details(
    static_finding,
    llm_finding
):

    category_score = (
        category_similarity(
            static_finding.get(
                "category"
            ),
            llm_finding.get(
                "category"
            )
        )
    )

    line_score = (
        line_similarity(
            static_finding.get(
                "line"
            ),
            llm_finding.get(
                "line"
            )
        )
    )

    message_score = (
        message_similarity(
            static_finding.get(
                "message"
            ),
            llm_finding.get(
                "message"
            )
        )
    )

    score = (
        CATEGORY_WEIGHT
        * category_score

        + LINE_WEIGHT
        * line_score

        + MESSAGE_WEIGHT
        * message_score
    )

    return {
        "score": score,
        "category_similarity": category_score,
        "line_similarity": line_score,
        "message_similarity": message_score
    }


def is_valid_match(details):

    return (
        details["score"]
        >= MATCH_THRESHOLD

        and

        details["message_similarity"]
        >= MIN_MESSAGE_SIMILARITY
    )


# ============================================================
# SEVERITY
# ============================================================

def merge_severity(
    static_severity,
    llm_severity
):

    static_normalized = (
        normalize_severity(
            static_severity
        )
    )

    llm_normalized = (
        normalize_severity(
            llm_severity
        )
    )

    if (
        SEVERITY_ORDER[
            static_normalized
        ]
        >=
        SEVERITY_ORDER[
            llm_normalized
        ]
    ):
        return static_normalized

    return llm_normalized


# ============================================================
# MERGE
# ============================================================

def create_hybrid_finding(
    static_finding,
    llm_finding,
    details
):

    return {
        "source": "hybrid",

        "category": (
            llm_finding.get(
                "category"
            )
            or static_finding.get(
                "category"
            )
        ),

        "line": (
            static_finding.get(
                "line"
            )
        ),

        "severity": merge_severity(
            static_finding.get(
                "severity"
            ),
            llm_finding.get(
                "severity"
            )
        ),

        "static_tool": (
            static_finding.get(
                "tool"
            )
        ),

        "static_code": (
            static_finding.get(
                "code"
            )
        ),

        "llm_code": (
            llm_finding.get(
                "code"
            )
        ),

        "message": (
            static_finding.get(
                "message"
            )
        ),

        "llm_explanation": (
            llm_finding.get(
                "explanation"
            )
        ),

        "suggested_fix": (
            llm_finding.get(
                "suggested_fix"
            )
        ),

        "confirmed_by": [
            static_finding.get(
                "tool"
            ),
            "llm"
        ],

        "match_score": round(
            details["score"],
            3
        ),

        "match_details": {
            "category_similarity": round(
                details[
                    "category_similarity"
                ],
                3
            ),

            "line_similarity": round(
                details[
                    "line_similarity"
                ],
                3
            ),

            "message_similarity": round(
                details[
                    "message_similarity"
                ],
                3
            )
        }
    }


# ============================================================
# MATCH FINDINGS
# ============================================================

def merge_findings(
    static_findings,
    llm_findings
):

    merged_findings = []

    used_llm_indexes = set()

    for static_finding in (
        static_findings
    ):

        best_index = None
        best_details = None

        for index, llm_finding in (
            enumerate(llm_findings)
        ):

            if index in used_llm_indexes:
                continue

            details = (
                calculate_match_details(
                    static_finding,
                    llm_finding
                )
            )

            if not is_valid_match(
                details
            ):
                continue

            if (
                best_details is None
                or details["score"]
                > best_details["score"]
            ):
                best_index = index
                best_details = details

        if best_index is not None:

            llm_finding = (
                llm_findings[
                    best_index
                ]
            )

            merged_findings.append(
                create_hybrid_finding(
                    static_finding,
                    llm_finding,
                    best_details
                )
            )

            used_llm_indexes.add(
                best_index
            )

        else:

            finding = dict(
                static_finding
            )

            finding["source"] = (
                "static"
            )

            merged_findings.append(
                finding
            )

    for index, llm_finding in (
        enumerate(llm_findings)
    ):

        if index in used_llm_indexes:
            continue

        finding = dict(
            llm_finding
        )

        finding["source"] = "llm"

        merged_findings.append(
            finding
        )

    return merged_findings


# ============================================================
# HYBRID ANALYSIS
# ============================================================

def run_hybrid_analysis(
    file_path,
    provider="mock"
):

    static_report = analyze_file(
        file_path
    )

    llm_report = analyze_with_llm(
        file_path,
        provider=provider
    )

    static_findings = (
        static_report.get(
            "findings",
            []
        )
    )

    llm_findings = (
        llm_report.get(
            "findings",
            []
        )
    )

    findings = merge_findings(
        static_findings,
        llm_findings
    )

    hybrid_confirmed = sum(
        1
        for finding in findings
        if finding.get(
            "source"
        ) == "hybrid"
    )

    return {
        "file": file_path,

        "analysis_mode": "hybrid",

        "llm_provider": provider,

        "llm_model": llm_report.get(
            "model"
        ),

        "summary": {
            "static_raw_findings": (
                len(static_findings)
            ),

            "llm_raw_findings": (
                len(llm_findings)
            ),

            "hybrid_confirmed": (
                hybrid_confirmed
            ),

            "unique_findings": (
                len(findings)
            )
        },

        "ast_analysis": (
            static_report.get(
                "ast_analysis"
            )
        ),

        "metrics": (
            static_report.get(
                "metrics",
                {}
            )
        ),

        "findings": findings
    }


# ============================================================
# SAVE
# ============================================================

def save_hybrid_report(
    report,
    output_file="hybrid_report.json"
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Hybrid Static + LLM Code Quality Analyzer"
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="samples/bad_code.py",
        help="Python file to analyze"
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "gemini"],
        default="mock",
        help="LLM provider"
    )

    args = parser.parse_args()

    report = run_hybrid_analysis(
        args.file,
        provider=args.provider
    )

    save_hybrid_report(
        report
    )

    print(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False
        )
    )