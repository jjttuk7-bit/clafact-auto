"""Batch orchestration for safe Structured Output slot enrichment."""

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from core.claim_parser import StructuredClaimExtractor
from core.claim_slot_enricher import enrich_claim_slots
from schemas.claim import ClaimSchema


def enrich_auto_registry_records(
    records: Iterable[Mapping[str, Any]], extractor: StructuredClaimExtractor
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Enrich AUTO_OK records only and retain a per-record audit outcome."""
    output: list[dict[str, Any]] = []
    summary = {
        "total_records": 0,
        "processed_records": 0,
        "ready_for_catalog_search": 0,
        "held_records": 0,
        "skipped_records": 0,
        "error_records": 0,
    }
    for source_record in records:
        summary["total_records"] += 1
        record = deepcopy(dict(source_record))
        claim = ClaimSchema.model_validate(record["claim"])
        if claim.parse_status != "AUTO_OK":
            record["slot_enrichment"] = {
                "status": "SKIPPED",
                "reason_code": "SOURCE_PARSE_NOT_AUTO_OK",
                "catalog_search_ready": False,
            }
            summary["skipped_records"] += 1
            output.append(record)
            continue

        summary["processed_records"] += 1
        try:
            result = enrich_claim_slots(claim, extractor)
        except Exception as error:  # External provider failures become an auditable hold.
            record["claim"] = claim.model_copy(
                update={"parse_status": "HOLD", "parse_reason": "SLOT_ENRICHMENT_ERROR"}
            ).model_dump(mode="json")
            record["slot_enrichment"] = {
                "status": "ERROR",
                "reason_code": type(error).__name__,
                "catalog_search_ready": False,
            }
            summary["error_records"] += 1
            output.append(record)
            continue

        record["claim"] = result.claim.model_dump(mode="json")
        record["slot_enrichment"] = {
            "status": "ENRICHED" if result.catalog_search_ready else "HOLD",
            "reason_code": result.reason_code,
            "catalog_search_ready": result.catalog_search_ready,
        }
        if result.catalog_search_ready:
            summary["ready_for_catalog_search"] += 1
        else:
            summary["held_records"] += 1
        output.append(record)
    return output, summary
