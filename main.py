import argparse
import json
import os

from analyzer.static_analyzer import analyze_file
from analyzer.llm_analyzer import analyze_with_llm
from analyzer.hybrid_analyzer import run_hybrid_analysis


def save_report(report, output_file):
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False
        )


def print_header():
    print("\n" + "=" * 60)
    print("AI-ASSISTED CODE QUALITY REVIEW")
    print("=" * 60)


def print_summary(report):
    print_header()

    print(f"\nFile: {report['file']}")
    print(f"Analysis mode: {report['analysis_mode']}")

    summary = report["summary"]

    print("\nRESULTS")
    print("-" * 30)

    print(
        f"Static findings: "
        f"{summary['static_raw_findings']}"
    )

    print(
        f"LLM findings: "
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


def main():
    parser = argparse.ArgumentParser(
        description="AI-Assisted Code Quality Review Tool"
    )

    parser.add_argument(
        "file",
        help="Python file to analyze"
    )

    parser.add_argument(
        "--mode",
        choices=["static", "llm", "hybrid"],
        default="hybrid",
        help="Analysis mode (default: hybrid)"
    )

    parser.add_argument(
        "--output",
        default="final_report.json",
        help="Output JSON file"
    )

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        return

    if not args.file.endswith(".py"):
        print("Error: Only Python files are currently supported.")
        return

    if args.mode == "static":
        report = analyze_file(args.file)

        # Give every mode a common identifier.
        report["analysis_mode"] = "static"

    elif args.mode == "llm":
        report = analyze_with_llm(args.file)

    else:
        report = run_hybrid_analysis(args.file)

    save_report(
        report,
        args.output
    )

    if args.mode == "hybrid":
        print_summary(report)

    else:
        print_header()
        print(f"\nFile: {args.file}")
        print(f"Analysis mode: {args.mode}")

    print(
        f"\nReport saved to: {args.output}"
    )


if __name__ == "__main__":
    main()