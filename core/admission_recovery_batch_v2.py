"""Batch serialization for slot-validated Admission recovery."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from core.admission_recovery import OfficialEvidenceResolver
from core.admission_recovery_v2 import recover_registry_record_v2
from core.claim_parser import StructuredClaimExtractor
from schemas.claim_registry import ClaimRegistryRecord


def run_admission_recovery_batch_v2(
    records: Iterable[ClaimRegistryRecord],
    *,
    extractor: StructuredClaimExtractor,
    official_service: OfficialEvidenceResolver,
    article_context_by_id: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    contexts = article_context_by_id or {}
    rows: list[dict[str, Any]] = []
    for record in records:
        recovery = recover_registry_record_v2(
            record,
            extractor=extractor,
            official_service=official_service,
            article_context=contexts.get(record.article_id),
        )
        rows.extend({
            "article_id": entry.record.article_id,
            "sentence_id": entry.record.sentence_id,
            "parent_claim_id": entry.parent_claim_id,
            "claim_id": entry.record.claim.claim_id,
            "source_sentence": entry.record.claim.source_sentence,
            "claim": entry.record.claim.model_dump(mode="json"),
            "recovery_action": recovery.recovery_action,
            "admission_route": entry.admission_route,
            "recovery_audit": entry.record.slot_enrichment,
            "official_resolution": _serialize(entry.official_resolution),
        } for entry in recovery.entries)
    return rows


def _serialize(resolution: Any) -> Any:
    if resolution is None or isinstance(resolution, (str, int, float, bool, dict, list)):
        return resolution
    verdict = getattr(resolution, "verdict", None)
    concept = getattr(resolution, "concept", None)
    candidates = getattr(resolution, "candidates", None)
    if verdict is None:
        return {"resolution_type": type(resolution).__name__}
    return {
        "concept": concept.model_dump(mode="json") if concept is not None else None,
        "candidate_count": len(candidates) if candidates is not None else 0,
        "verdict": verdict.model_dump(mode="json"),
    }
