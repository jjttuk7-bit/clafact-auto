"""Run only a bounded record-comparison Claim group through the canonical v3 engine."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.canonical_pipeline import build_canonical_pipeline
from core.claim_registry_loader import load_claim_registry
from core.pipeline_run_reporting import serialize_pipeline_entry
from core.record_comparison_splitter import split_record_comparison_claim
from schemas.claim_registry import ClaimRegistryRecord


MAX_GROUP_SIZE = 20
CSV_FIELDS = (
    "run_id", "article_id", "sentence_id", "parent_claim_id", "child_claim_id",
    "source_sentence", "before_parse_status", "before_parse_reason", "child_type",
    "after_status", "after_reason", "official_table", "history_period_range",
    "requested_period_range", "requested_period_count", "observed_count",
    "record_value", "record_unit", "record_periods",
    "source_urls", "response_hashes", "official_api_verified",
    "publication_evidence_scope", "publication_reference_period",
    "publication_coverage", "value_last_changed_dates",
    "official_trace_json", "stage_results_json",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.claim_ids and args.limit is None:
        parser.error("one or more --claim-id values or a bounded --limit is required")
    if args.limit is not None and not 1 <= args.limit <= MAX_GROUP_SIZE:
        parser.error(f"--limit must be between 1 and {MAX_GROUP_SIZE}")
    if len(args.claim_ids) > MAX_GROUP_SIZE:
        parser.error(f"at most {MAX_GROUP_SIZE} --claim-id values are allowed")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.run_id):
        parser.error("--run-id may contain only letters, digits, dot, underscore, and hyphen")
    jsonl_path = args.output_dir / f"{args.run_id}.jsonl"
    csv_path = args.output_dir / f"{args.run_id}.csv"
    if jsonl_path.exists() or csv_path.exists():
        parser.error("run output already exists; use a new --run-id")

    settings = Settings()
    if not settings.kosis_api_key:
        parser.error("KOSIS_API_KEY is required")
    loaded = load_claim_registry(args.registry_path)
    if loaded.errors:
        parser.error(f"Registry contains {len(loaded.errors)} invalid row(s)")
    try:
        records = select_records(loaded.records, claim_ids=args.claim_ids, limit=args.limit)
    except ValueError as error:
        parser.error(str(error))

    runtime = build_canonical_pipeline(
        settings,
        live_time_budget_seconds=args.live_budget_seconds,
        structured_extraction_enabled=False,
    )
    json_rows: list[dict[str, Any]] = []
    csv_rows: list[dict[str, str]] = []
    for record in records:
        entries = runtime.verify_record(
            record, allow_structured_recovery=True,
        )
        for entry in entries:
            serialized = serialize_pipeline_entry(record, entry)
            enriched = {
                "run_id": args.run_id,
                "before_parse_status": record.claim.parse_status,
                "before_parse_reason": record.claim.parse_reason,
                **serialized,
            }
            json_rows.append(enriched)
            csv_rows.append(_csv_row(enriched))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in json_rows),
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(json.dumps({
        "run_id": args.run_id,
        "input_claims": len(records),
        "derived_claims": len(json_rows),
        "csv": str(csv_path),
        "jsonl": str(jsonl_path),
    }, ensure_ascii=False))
    return 0


def select_records(
    records: Sequence[ClaimRegistryRecord], *, claim_ids: Sequence[str], limit: int | None,
) -> list[ClaimRegistryRecord]:
    requested = list(dict.fromkeys(claim_ids))
    if requested:
        by_id = {record.claim.claim_id: record for record in records}
        missing = [claim_id for claim_id in requested if claim_id not in by_id]
        if missing:
            raise ValueError("Claim ID not found: " + ", ".join(missing))
        selected = [by_id[claim_id] for claim_id in requested]
    else:
        selected = [record for record in records if len(split_record_comparison_claim(record.claim)) == 2]
        selected = selected[:limit]
    if not selected:
        raise ValueError("No source-grounded record comparison Claims were selected")
    if len(selected) > MAX_GROUP_SIZE:
        raise ValueError(f"Selected group exceeds the {MAX_GROUP_SIZE}-Claim safety limit")
    return selected


def _csv_row(row: dict[str, Any]) -> dict[str, str]:
    claim = _dict(row.get("claim"))
    resolution = _dict(row.get("official_resolution"))
    verdict = _dict(resolution.get("verdict"))
    record = _dict(verdict.get("record_comparison"))
    provenance = [_dict(item) for item in verdict.get("official_value_provenance") or []]
    evidence = [_dict(item) for item in verdict.get("evidence_cells") or []]
    candidates = [_dict(item) for item in resolution.get("candidates") or []]
    coordinate = evidence[0] if evidence else (candidates[0] if candidates else {})
    org_id = str(coordinate.get("org_id") or "")
    table_id = str(coordinate.get("tbl_id") or "")
    requested_periods = [str(item.get("prd_de") or "") for item in evidence if item.get("prd_de")]
    source_urls = _unique(str(item.get("source_url") or "") for item in provenance)
    hashes = _unique(str(
        item.get("content_hash") or item.get("response_hash") or item.get("snapshot_hash") or ""
    ) for item in provenance)
    publications = [_dict(item.get("publication")) for item in provenance]
    publication_scopes = _unique(
        str(item.get("evidence_scope") or "") for item in publications
    )
    publication_references = _unique(
        str(item.get("reference_period") or "") for item in publications
    )
    publication_coverages = _unique(
        f"{item.get('coverage_start_period')}~{item.get('coverage_end_period')}"
        for item in publications
        if item.get("coverage_start_period") and item.get("coverage_end_period")
    )
    value_last_changed_dates = [
        str(item.get("value_last_changed_at") or "")
        for item in provenance
        if item.get("value_last_changed_at")
    ]
    api_verified = (
        bool(evidence)
        and len(provenance) == len(evidence)
        and all(
            item.get("source") == "API"
            and _dict(item.get("publication")).get("status") == "VERIFIED"
            for item in provenance
        )
    )
    return {
        "run_id": str(row.get("run_id") or ""),
        "article_id": str(row.get("article_id") or ""),
        "sentence_id": str(row.get("sentence_id") or ""),
        "parent_claim_id": str(row.get("parent_claim_id") or ""),
        "child_claim_id": str(row.get("claim_id") or ""),
        "source_sentence": str(row.get("source_sentence") or ""),
        "before_parse_status": str(row.get("before_parse_status") or ""),
        "before_parse_reason": str(row.get("before_parse_reason") or ""),
        "child_type": str(claim.get("calculation") or "DIRECT_VALUE"),
        "after_status": str(verdict.get("route_status") or row.get("terminal_status") or ""),
        "after_reason": str(verdict.get("reason_code") or row.get("reason_code") or ""),
        "official_table": f"{org_id}:{table_id}" if org_id and table_id else "",
        "history_period_range": _period_range(record),
        "requested_period_range": _requested_period_range(requested_periods),
        "requested_period_count": str(len(requested_periods)),
        "observed_count": str(record.get("observed_count") or ""),
        "record_value": str(record.get("record_value") if record.get("record_value") is not None else ""),
        "record_unit": str(record.get("record_unit") or ""),
        "record_periods": "|".join(str(value) for value in record.get("record_periods") or []),
        "source_urls": "|".join(source_urls),
        "response_hashes": "|".join(hashes),
        "official_api_verified": "true" if api_verified else "false",
        "publication_evidence_scope": "|".join(publication_scopes),
        "publication_reference_period": "|".join(publication_references),
        "publication_coverage": "|".join(publication_coverages),
        "value_last_changed_dates": "|".join(value_last_changed_dates),
        "official_trace_json": json.dumps(verdict.get("execution_trace") or {}, ensure_ascii=False, sort_keys=True),
        "stage_results_json": json.dumps(row.get("stage_results") or [], ensure_ascii=False, sort_keys=True),
    }


def _period_range(record: dict[str, Any]) -> str:
    start = str(record.get("start_period") or "")
    end = str(record.get("end_period") or "")
    return f"{start}~{end}" if start and end else ""


def _requested_period_range(periods: list[str]) -> str:
    return f"{periods[0]}~{periods[-1]}" if periods else ""


def _unique(values) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--claim-id", dest="claim_ids", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--live-budget-seconds", type=float, default=45.0)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
