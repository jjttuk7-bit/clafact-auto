"""Merge audited slot-enrichment rows into a source-preserving derived Registry."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.registry_enrichment_merge import merge_enriched_registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-registry", required=True, type=Path)
    parser.add_argument("--enriched-registry", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    paths = merge_enriched_registry(
        source_path=args.source_registry,
        enriched_path=args.enriched_registry,
        output_dir=args.output_dir,
    )
    print(f"Derived registry: {paths.registry_path}")
    print(f"Merge report: {paths.report_path}")


if __name__ == "__main__":
    main()
