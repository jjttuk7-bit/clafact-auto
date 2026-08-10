"""LLM-free batch enrichment for explicitly stated ClaimSchema slots."""

from collections import Counter
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from core.deterministic_slot_enricher import infer_explicit_slots
from schemas.claim import ClaimSchema


def enrich_registry_records_deterministically(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Copy Registry records and enrich only safely interpretable AUTO_OK claims."""
    output: list[dict[str, Any]] = []
    summary = {
        "total_records": 0,
        "processed_records": 0,
        "ready_for_catalog_search": 0,
        "held_records": 0,
        "skipped_records": 0,
    }
    for source_record in records:
        summary["total_records"] += 1
        record = deepcopy(dict(source_record))
        claim = ClaimSchema.model_validate(record["claim"])
        if claim.parse_status != "AUTO_OK":
            record["deterministic_slot_enrichment"] = {
                "status": "SKIPPED",
                "reason_code": "SOURCE_PARSE_NOT_AUTO_OK",
                "catalog_search_ready": False,
            }
            summary["skipped_records"] += 1
            output.append(record)
            continue

        summary["processed_records"] += 1
        explicit = infer_explicit_slots(claim.source_sentence)
        if explicit.reason_code is not None:
            record["claim"] = claim.model_copy(
                update={"parse_status": "HOLD", "parse_reason": explicit.reason_code}
            ).model_dump(mode="json")
            record["deterministic_slot_enrichment"] = {
                "status": "HOLD",
                "reason_code": explicit.reason_code,
                "catalog_search_ready": False,
            }
            summary["held_records"] += 1
            output.append(record)
            continue

        enriched = claim.model_copy(
            update={
                "comparison": claim.comparison or explicit.comparison,
                "calculation": claim.calculation or explicit.calculation,
                "condition": claim.condition or explicit.condition,
            }
        )
        ready = enriched.calculation is not None and (
            enriched.calculation != "GROWTH_RATE" or enriched.comparison is not None
        )
        if not ready:
            reason_code = "MISSING_CALCULATION"
            record["claim"] = enriched.model_copy(
                update={"parse_status": "HOLD", "parse_reason": reason_code}
            ).model_dump(mode="json")
            record["deterministic_slot_enrichment"] = {
                "status": "HOLD",
                "reason_code": reason_code,
                "catalog_search_ready": False,
            }
            summary["held_records"] += 1
        else:
            record["claim"] = enriched.model_dump(mode="json")
            record["deterministic_slot_enrichment"] = {
                "status": "ENRICHED",
                "reason_code": None,
                "catalog_search_ready": True,
            }
            summary["ready_for_catalog_search"] += 1
        output.append(record)
    return output, summary

def build_deterministic_enrichment_report(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize only values present in deterministic enrichment output records."""
    materialized = [dict(record) for record in records]
    status_counts = Counter(
        record["deterministic_slot_enrichment"]["status"] for record in materialized
    )
    parse_status_counts = Counter(record["claim"]["parse_status"] for record in materialized)
    slot_filled_counts = {
        slot: sum(record["claim"].get(slot) not in (None, "", {}) for record in materialized)
        for slot in ("comparison", "calculation", "condition")
    }
    hold_reason_counts = Counter(
        record["deterministic_slot_enrichment"]["reason_code"]
        for record in materialized
        if record["deterministic_slot_enrichment"]["status"] == "HOLD"
        and record["deterministic_slot_enrichment"]["reason_code"] is not None
    )
    return {
        "total_records": len(materialized),
        "enrichment_status_counts": dict(sorted(status_counts.items())),
        "parse_status_counts": dict(sorted(parse_status_counts.items())),
        "slot_filled_counts": slot_filled_counts,
        "hold_reason_counts": dict(sorted(hold_reason_counts.items())),
    }
