"""Reclassify only explicitly selected, source-grounded period change amounts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.claim_registry_loader import load_claim_registry
from core.validated_claim_recovery import recover_validated_claim
from schemas.claim_registry import ClaimRegistryRecord


MAX_GROUP_SIZE = 20
RECLASSIFICATION_REASON = "SOURCE_GROUNDED_PERIOD_CHANGE_AMOUNT"
CSV_FIELDS = (
    "claim_id",
    "article_id",
    "source_sentence",
    "target_numeric_expression",
    "before_calculation",
    "after_calculation",
    "comparison_type",
    "direction",
    "result",
    "reason",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.claim_ids:
        parser.error("one or more explicit --claim-id values are required")
    requested = list(dict.fromkeys(args.claim_ids))
    if len(requested) > MAX_GROUP_SIZE:
        parser.error(f"at most {MAX_GROUP_SIZE} --claim-id values are allowed")
    if args.output_registry.exists() or args.audit_csv.exists():
        parser.error("output already exists; choose new output paths")

    loaded = load_claim_registry(args.source_registry)
    if loaded.errors:
        parser.error(f"Registry contains {len(loaded.errors)} invalid row(s)")
    try:
        selected = _select_records(loaded.records, requested)
    except ValueError as error:
        parser.error(str(error))

    corrected: list[ClaimRegistryRecord] = []
    audit_rows: list[dict[str, str]] = []
    for record in selected:
        before = record.claim
        enrichment = dict(record.slot_enrichment or {})
        expression = str(enrichment.get("target_numeric_expression") or "").strip()
        recovered = (
            recover_validated_claim(
                before,
                record.article_published_at,
                source_value_text=expression,
            )
            if expression
            else before
        )
        changed = (
            before.calculation != recovered.calculation
            and recovered.calculation == "DIFFERENCE"
            and (recovered.comparison or {}).get("operand_source") == "OFFICIAL_EVIDENCE"
        )
        reason = RECLASSIFICATION_REASON if changed else (
            "TARGET_NUMERIC_EXPRESSION_MISSING" if not expression
            else "SOURCE_CHANGE_AMOUNT_NOT_CONFIRMED"
        )
        if changed:
            enrichment.update(
                change_amount_reclassified=True,
                previous_calculation=before.calculation,
                reclassification_reason=reason,
            )
            corrected.append(record.model_copy(update={
                "claim": recovered,
                "slot_enrichment": enrichment,
            }))
        audit_rows.append({
            "claim_id": before.claim_id,
            "article_id": record.article_id,
            "source_sentence": before.source_sentence,
            "target_numeric_expression": expression,
            "before_calculation": before.calculation or "",
            "after_calculation": recovered.calculation or "",
            "comparison_type": str((recovered.comparison or {}).get("type") or ""),
            "direction": str((recovered.condition or {}).get("direction") or ""),
            "result": "RECLASSIFIED" if changed else "NOT_RECLASSIFIED",
            "reason": reason,
        })

    args.output_registry.parent.mkdir(parents=True, exist_ok=True)
    args.audit_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_registry.write_text(
        "".join(record.model_dump_json() + "\n" for record in corrected),
        encoding="utf-8",
    )
    with args.audit_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(audit_rows)
    print(json.dumps({
        "requested": len(selected),
        "reclassified": len(corrected),
        "output_registry": str(args.output_registry),
        "audit_csv": str(args.audit_csv),
    }, ensure_ascii=False))
    return 0


def _select_records(
    records: Sequence[ClaimRegistryRecord], claim_ids: Sequence[str],
) -> list[ClaimRegistryRecord]:
    by_id = {record.claim.claim_id: record for record in records}
    missing = [claim_id for claim_id in claim_ids if claim_id not in by_id]
    if missing:
        raise ValueError("Claim ID not found: " + ", ".join(missing))
    return [by_id[claim_id] for claim_id in claim_ids]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_registry", type=Path)
    parser.add_argument("output_registry", type=Path)
    parser.add_argument("audit_csv", type=Path)
    parser.add_argument("--claim-id", dest="claim_ids", action="append", default=[])
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
