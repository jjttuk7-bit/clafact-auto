"""Run LLM-free Claim Registry slot enrichment into a separate output directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.deterministic_slot_enrichment_batch import (
    build_deterministic_enrichment_report,
    enrich_registry_records_deterministically,
)


def run(source_path: Path, output_dir: Path) -> tuple[Path, Path]:
    """Read a Registry JSONL and write deterministic enrichment artifacts."""
    records = [
        json.loads(line)
        for line in source_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    enriched_records, _ = enrich_registry_records_deterministically(records)
    report = build_deterministic_enrichment_report(enriched_records)
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "deterministic_enriched_claims.jsonl"
    report_path = output_dir / "coverage_report.json"
    records_path.write_text(
        "\n".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True)
            for record in enriched_records
        )
        + ("\n" if enriched_records else ""),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return records_path, report_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    records_path, report_path = run(args.registry, args.output_dir)
    print(f"Enriched records: {records_path}")
    print(f"Coverage report: {report_path}")


if __name__ == "__main__":
    main()
