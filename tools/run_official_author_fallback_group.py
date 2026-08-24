"""Run exactly one frozen official-author fallback group through the canonical pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.canonical_pipeline import build_canonical_pipeline
from core.claim_registry_loader import load_claim_registry
from core.official_run_csv import write_official_run_csv
from core.pipeline_run_reporting import build_run_report, serialize_pipeline_entry
from schemas.claim_registry import ClaimRegistryRecord


EXPECTED_GROUP_SIZE = 5


def select_frozen_records(
    records: Sequence[ClaimRegistryRecord],
    frozen_rows: Sequence[dict[str, Any]],
    *,
    expected_count: int = EXPECTED_GROUP_SIZE,
) -> list[ClaimRegistryRecord]:
    claim_ids = [str(row.get("claim_id") or "") for row in frozen_rows]
    if (
        len(claim_ids) != expected_count
        or any(not claim_id for claim_id in claim_ids)
        or len(set(claim_ids)) != expected_count
    ):
        raise ValueError("FROZEN_CLAIM_IDS_INVALID")
    by_id = {record.claim.claim_id: record for record in records}
    missing = [claim_id for claim_id in claim_ids if claim_id not in by_id]
    if missing:
        raise ValueError("FROZEN_CLAIM_ID_NOT_FOUND:" + ",".join(missing))
    return [by_id[claim_id] for claim_id in claim_ids]


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    settings = Settings()
    if not settings.kosis_api_key:
        parser.error("KOSIS_API_KEY is required")

    loaded = load_claim_registry(args.registry)
    if loaded.errors:
        parser.error(f"Registry contains {len(loaded.errors)} invalid row(s)")
    frozen_rows = _read_jsonl(args.frozen)
    try:
        records = select_frozen_records(
            loaded.records,
            frozen_rows,
            expected_count=args.expected_count,
        )
    except ValueError as error:
        parser.error(str(error))

    runtime = build_canonical_pipeline(
        settings,
        live_time_budget_seconds=args.live_budget_seconds,
        structured_extraction_enabled=False,
    )
    results: list[dict[str, Any]] = []
    for record in records:
        entries = runtime.verify_record(record, allow_structured_recovery=False)
        if len(entries) != 1:
            raise RuntimeError(
                f"OFFICIAL_AUTHOR_GROUP_DERIVED_COUNT_MISMATCH:{record.claim.claim_id}:{len(entries)}"
            )
        results.append(serialize_pipeline_entry(record, entries[0]))

    output_ids = [str(row.get("claim_id") or "") for row in results]
    expected_ids = [record.claim.claim_id for record in records]
    if output_ids != expected_ids:
        raise RuntimeError("OFFICIAL_AUTHOR_GROUP_OUTPUT_ID_MISMATCH")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "results.jsonl"
    csv_path = args.output_dir / "results.csv"
    report_path = args.output_dir / "coverage_report.json"
    _write_jsonl(results_path, results)
    write_official_run_csv(
        records,
        results,
        csv_path,
        code_version=args.code_version,
        data_version=args.data_version,
    )
    report = build_run_report(
        results,
        input_count=len(records),
        registry_errors=loaded.errors,
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "input_claims": len(records),
        "output_claims": len(results),
        "results": str(results_path),
        "csv": str(csv_path),
        "report": str(report_path),
    }, ensure_ascii=False))
    return 0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=EXPECTED_GROUP_SIZE)
    parser.add_argument("--live-budget-seconds", type=float, default=45.0)
    parser.add_argument("--code-version", default="official-author-fallback-v1")
    parser.add_argument("--data-version", default="official-author-profiles-v1")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
