"""Single Article/Registry orchestration path for Admission recovery and KOSIS evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import Any

from core.admission_recovery import OfficialEvidenceResolver
from core.admission_recovery_v3 import recover_registry_record_v3
from core.article_claim_pipeline import parse_article_claims
from core.claim_parser import StructuredClaimExtractor
from core.operational_error import OperationalStageError
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


@dataclass(frozen=True, slots=True)
class PipelineEntry:
    parent_claim_id: str
    claim: ClaimSchema
    recovery_action: str
    admission_route: str
    terminal_status: str
    reason_code: str | None
    official_resolution: Any | None


@dataclass(frozen=True, slots=True)
class ArticlePipelineResult:
    article_id: str
    entries: list[PipelineEntry]


def verify_article(article_text: str, *, article_published_at: date | None, extractor: StructuredClaimExtractor, official_service: OfficialEvidenceResolver, article_id: str | None = None) -> ArticlePipelineResult:
    """Run every numerical Claim through split, 12 slots, re-Admission, and KOSIS."""
    stable_article_id = article_id or _article_id(article_text)
    claims = parse_article_claims(article_text, extractor, article_published_at=article_published_at)
    entries: list[PipelineEntry] = []
    for index, claim in enumerate(claims, start=1):
        record = ClaimRegistryRecord(article_id=stable_article_id, sentence_id=str(index), article_published_at=article_published_at, source_ref="unified_claim_pipeline_v2", claim=claim)
        try:
            recovery = recover_registry_record_v3(record, extractor=extractor, official_service=official_service, article_context=article_text)
        except OperationalStageError as error:
            entries.append(PipelineEntry(claim.claim_id, claim, "NO_RECOVERY", "KOSIS_PIPELINE_ELIGIBLE", "HOLD", f"{error.stage}_UNAVAILABLE", None))
            continue
        for recovered in recovery.entries:
            status, reason = _terminal_result(recovered.official_resolution, recovered.admission_route, article_published_at, recovered.record.claim)
            entries.append(PipelineEntry(recovered.parent_claim_id, recovered.record.claim, recovery.recovery_action, recovered.admission_route, status, reason, recovered.official_resolution))
    return ArticlePipelineResult(stable_article_id, entries)


def _terminal_result(resolution: Any | None, admission_route: str, article_published_at: date | None, claim: ClaimSchema) -> tuple[str, str | None]:
    if resolution is not None:
        verdict = getattr(resolution, "verdict", None)
        if verdict is None and isinstance(resolution, dict): return str(resolution.get("route_status") or "HOLD"), resolution.get("reason_code")
        return str(getattr(verdict, "route_status", "HOLD")), getattr(verdict, "reason_code", None)
    if article_published_at is None and admission_route == "KOSIS_PIPELINE_ELIGIBLE": return "HOLD", "ARTICLE_DATE_REQUIRED"
    return "HOLD", claim.parse_reason or admission_route


def _article_id(article_text: str) -> str:
    return f"article_{sha256(article_text.strip().encode('utf-8')).hexdigest()[:16]}"
