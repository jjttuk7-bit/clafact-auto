"""Build a provenance-preserving Claim Registry from a CSV/XLSX source tab."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.claim_registry import build_registry_from_source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--sheet-name")
    parser.add_argument("--header-row", type=int, default=1)
    parser.add_argument("--article-input", type=Path)
    parser.add_argument("--article-sheet-name")
    parser.add_argument("--article-header-row", type=int, default=1)
    args = parser.parse_args()

    jsonl_path, report_path = build_registry_from_source(
        args.input,
        source_ref=args.source_ref,
        output_dir=args.output_dir,
        expected_count=args.expected_count,
        source_sheet=args.sheet_name,
        header_row=args.header_row,
        date_source_path=args.article_input,
        date_sheet=args.article_sheet_name,
        date_header_row=args.article_header_row,
    )
    print(f"Registry: {jsonl_path}")
    print(f"Validation report: {report_path}")


if __name__ == "__main__":
    main()
