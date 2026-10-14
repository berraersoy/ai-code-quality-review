import argparse
import json

from analyzer.static_analyzer import analyze_file
from analyzer.llm_analyzer import analyze_with_llm
from analyzer.hybrid_analyzer import run_hybrid_analysis


def save_report(
    report,
    output_file
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


def main():

    parser = argparse.ArgumentParser(
        description=(
            "AI-Assisted Python "
            "Code Quality Review Tool"
        )
    )

    parser.add_argument(
        "file",
        help="Python file to analyze"
    )

    parser.add_argument(
        "--mode",
        choices=[
            "static",
            "llm",
            "hybrid"
        ],
        default="hybrid",
        help="Analysis mode"
    )

    parser.add_argument(
        "--provider",
        choices=[
            "mock",
            "gemini"
        ],
        default="mock",
        help="LLM provider"
    )

    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file"
    )

    args = parser.parse_args()

    if args.mode == "static":

        report = analyze_file(
            args.file
        )

        default_output = (
            "report.json"
        )

    elif args.mode == "llm":

        report = analyze_with_llm(
            args.file,
            provider=args.provider
        )

        default_output = (
            "llm_report.json"
        )

    else:

        report = run_hybrid_analysis(
            args.file,
            provider=args.provider
        )

        default_output = (
            "final_report.json"
        )

    output_file = (
        args.output
        if args.output
        else default_output
    )

    save_report(
        report,
        output_file
    )

    print(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False
        )
    )

    print(
        f"\nReport saved to: "
        f"{output_file}"
    )


if __name__ == "__main__":
    import sys

    try:
        main()
    except (RuntimeError, ValueError, FileNotFoundError) as error:
        print(f"\n[ERROR] {error}", file=sys.stderr)
        sys.exit(1)