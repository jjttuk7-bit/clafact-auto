"""Batch execution through the same OfficialEvidenceService used by new Claims."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any, Protocol

from core.claim_parse_reason import operational_parse_reason
from core.official_evidence_service import OfficialEvidenceService
from core.operational_error import OperationalStageError
from schemas.claim_registry import ClaimRegistryRecord


class OfficialEvidenceResolver(Protocol):
    def resolve(self, claim, *, article_date: date): ...


def run_official_e2e_batch(
    records: Iterable[ClaimRegistryRecord],
    service: OfficialEvidenceResolver,
    *,
    start: int = 0,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Run a stable Registry slice through the shared official evidence engine."""
    if start < 0:
        raise ValueError("start must be non-negative")
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least one")
    materialized = list(records)
    selected = materialized[start:] if limit is None else materialized[start : start + limit]
    rows: list[dict[str, Any]] = []
    for record in selected:
        claim = record.claim
        if claim.parse_status != "AUTO_OK":
            rows.append(_parse_hold(record, operational_parse_reason(claim.parse_reason)))
            continue
        if record.article_published_at is None:
            rows.append(_parse_hold(record, "ARTICLE_DATE_REQUIRED"))
            continue
        try:
            resolution = service.resolve(claim, article_date=record.article_published_at)
        except OperationalStageError as error:
            rows.append(_operational_hold(record, error))
            continue
        verdict = resolution.verdict.model_dump(mode="json")
        rows.append({
            "article_id": record.article_id,
            "sentence_id": record.sentence_id,
            "claim_id": claim.claim_id,
            "source_sentence": claim.source_sentence,
            "concept": resolution.concept.model_dump(mode="json"),
            "candidate_metadata": {"count": len(resolution.candidates)},
            "official_value": verdict["calculated_value"],
            **verdict,
        })
    return rows


def _parse_hold(record: ClaimRegistryRecord, reason_code: str) -> dict[str, Any]:
    claim = record.claim
    return {
        "article_id": record.article_id,
        "sentence_id": record.sentence_id,
        "claim_id": claim.claim_id,
        "source_sentence": claim.source_sentence,
        "route_status": "HOLD",
        "reason_code": reason_code,
        "verdict": "UNDETERMINED",
        "claim_value": claim.value,
        "evidence_values": [],
        "calculated_value": None,
        "official_value": None,
        "candidate_metadata": {"count": 0},
        "parse_reason_detail": claim.parse_reason,
    }


def _operational_hold(record: ClaimRegistryRecord, error: OperationalStageError) -> dict[str, Any]:
    row = _parse_hold(record, f"{error.stage}_UNAVAILABLE")
    row["diagnostic_id"] = error.diagnostic_id
    return row