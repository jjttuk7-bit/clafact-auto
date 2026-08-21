"""Derive safe 12-slot quality and Concept artifacts from enriched registry rows."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.claim_splitter import split_complex_claim
from core.data_loader import load_standard_concepts
from core.semantic_normalizer import normalize_concept
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema


_SLOT_NAMES = (
    "indicator",
    "value",
    "unit",
    "time",
    "frequency",
    "region",
    "population",
    "dimension",
    "comparison",
    "calculation",
    "condition",
    "source_hint",
)


@dataclass(frozen=True)
class RegistryBatchDerivation:
    """Derived registry, unambiguous concepts, quality report, and review queue."""

    records: list[ClaimRegistryRecord]
    concepts: Mapping[tuple[str, str], StandardConceptSchema]
    quality_report: dict[str, Any]
    review_queue: list[dict[str, Any]]


def derive_registry_batch(
    enriched_rows: Iterable[Mapping[str, Any]], standard_path: Path
) -> RegistryBatchDerivation:
    """Keep source rows immutable while deriving only safe downstream artifacts."""
    concepts = load_standard_concepts(standard_path)
    records = [ClaimRegistryRecord.model_validate(_registry_payload(row)) for row in enriched_rows]
    route_counts = Counter(record.claim.parse_status for record in records)
    hold_reasons: Counter[str] = Counter()
    error_reasons: Counter[str] = Counter()
    concept_sidecar: dict[tuple[str, str], StandardConceptSchema] = {}
    review_queue: list[dict[str, Any]] = []
    split_candidates = 0

    for record, source_row in zip(records, enriched_rows, strict=True):
        enrichment = dict(source_row.get("slot_enrichment") or {})
        reason = record.claim.parse_reason or enrichment.get("reason_code")
        needs_split = len(split_complex_claim(record.claim.source_sentence)) > 1
        if needs_split:
            split_candidates += 1

        concept_reason: str | None = None
        if record.claim.parse_status == "AUTO_OK":
            concept = normalize_concept(record.claim, concepts)
            if concept.status == "MATCHED":
                concept_sidecar[(record.article_id, record.sentence_id)] = concept
            else:
                concept_reason = "CONCEPT_UNRESOLVED"

        if enrichment.get("status") == "ERROR":
            error_reasons[str(reason or "SLOT_ENRICHMENT_ERROR")] += 1
        elif record.claim.parse_status != "AUTO_OK":
            hold_reasons[str(reason or "CLAIM_NOT_AUTO_OK")] += 1

        review_reason = reason
        if record.claim.parse_status == "AUTO_OK" and concept_reason:
            hold_reasons[concept_reason] += 1
            review_reason = concept_reason
        if record.claim.parse_status != "AUTO_OK" or enrichment.get("status") == "ERROR" or concept_reason:
            review_queue.append(
                {
                    "article_id": record.article_id,
                    "sentence_id": record.sentence_id,
                    "claim_id": record.claim.claim_id,
                    "parse_status": record.claim.parse_status,
                    "reason_code": review_reason or "REVIEW_REQUIRED",
                    "needs_claim_split": needs_split,
                    "source_sentence": record.claim.source_sentence,
                }
            )

    total = len(records)
    completion = {
        slot: {
            "filled": sum(getattr(record.claim, slot) is not None for record in records),
            "total": total,
            "rate": (sum(getattr(record.claim, slot) is not None for record in records) / total) if total else 0.0,
        }
        for slot in _SLOT_NAMES
    }
    report = {
        "total_records": total,
        "slot_completion": completion,
        "route_counts": dict(sorted(route_counts.items())),
        "hold_reason_counts": dict(sorted(hold_reasons.items())),
        "error_reason_counts": dict(sorted(error_reasons.items())),
        "matched_concepts": len(concept_sidecar),
        "unresolved_concepts": total - len(concept_sidecar) - sum(
            record.claim.parse_status != "AUTO_OK" for record in records
        ),
        "claim_split_candidates": split_candidates,
        "review_queue_count": len(review_queue),
    }
    return RegistryBatchDerivation(records, concept_sidecar, report, review_queue)


def _registry_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Discard enrichment-only fields before strict registry validation."""
    allowed = {"article_id", "sentence_id", "article_published_at", "source_ref", "source_metadata", "claim", "review_status"}
    return {key: value for key, value in row.items() if key in allowed}
