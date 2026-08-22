"""Single Article/Registry orchestration path for Admission recovery and KOSIS evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import Any

from core.admission_recovery import OfficialEvidenceResolver
from core.admission_recovery_v3 import recover_registry_record_v3
from core.claim_admissibility import classify_admissibility
from core.article_claim_pipeline import parse_article_claims
from core.claim_lineage import ClaimLineageRecord
from core.claim_parser import StructuredClaimExtractor
from core.operational_error import OperationalStageError, run_operational_stage
from core.recovery_stage_audit import build_recovery_stage_audit
from core.slot_audit import audit_claim_slots
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.slot_audit import SlotAuditSchema
from schemas.stage_result import StageResultSchema


@dataclass(frozen=True, slots=True)
class PipelineEntry:
    parent_claim_id: str
    claim: ClaimSchema
    recovery_action: str
    admission_route: str
    terminal_status: str
    reason_code: str | None
    official_resolution: Any | None
    diagnostic_id: str | None = None
    lineage_record: ClaimLineageRecord | None = None
    stage_results: tuple[StageResultSchema, ...] = ()
    slot_audit: SlotAuditSchema | None = None


@dataclass(frozen=True, slots=True)
class ArticlePipelineResult:
    article_id: str
    entries: list[PipelineEntry]


def verify_article(
    article_text: str,
    *,
    article_published_at: date | None,
    extractor: StructuredClaimExtractor,
    official_service: OfficialEvidenceResolver,
    article_id: str | None = None,
) -> ArticlePipelineResult:
    """Run every numerical Claim through the canonical record-level pipeline."""
    stable_article_id = article_id or _article_id(article_text)
    claims = run_operational_stage(
        "CLAIM_PARSE",
        lambda: parse_article_claims(
            article_text,
            extractor,
            article_published_at=article_published_at,
        ),
    )
    entries: list[PipelineEntry] = []
    for index, claim in enumerate(claims, start=1):
        record = ClaimRegistryRecord(
            article_id=stable_article_id,
            sentence_id=str(index),
            article_published_at=article_published_at,
            source_ref="unified_claim_pipeline_v3",
            claim=claim,
        )
        entries.extend(
            verify_registry_record(
                record,
                extractor=extractor,
                official_service=official_service,
                article_context=article_text,
            )
        )
    return ArticlePipelineResult(stable_article_id, entries)


def verify_registry_record(
    record: ClaimRegistryRecord,
    *,
    extractor: StructuredClaimExtractor,
    official_service: OfficialEvidenceResolver,
    article_context: str | None = None,
    allow_structured_recovery: bool = True,
) -> list[PipelineEntry]:
    """Verify one Registry record through the same recovery used by articles."""
    try:
        if allow_structured_recovery:
            recovery = recover_registry_record_v3(
                record,
                extractor=extractor,
                official_service=official_service,
                article_context=article_context,
            )
        else:
            return [_verify_stored_claim(record, official_service)]
    except OperationalStageError as error:
        return [
            PipelineEntry(
                record.claim.claim_id,
                record.claim,
                "NO_RECOVERY",
                "KOSIS_PIPELINE_ELIGIBLE",
                "HUMAN_REVIEW" if error.stage in {"CLAIM_PARSE", "CLAIM_SPLIT"} else "HOLD",
                f"{error.stage}_UNAVAILABLE",
                None,
                error.diagnostic_id,
            )
        ]

    entries: list[PipelineEntry] = []
    for child_ordinal, recovered in enumerate(recovery.entries, start=1):
        enrichment = (
            recovered.record.slot_enrichment
            if isinstance(recovered.record.slot_enrichment, dict)
            else {}
        )
        status, reason = _terminal_result(
            recovered.official_resolution,
            recovered.admission_route,
            record.article_published_at,
            recovered.record.claim,
        )
        lineage, stage_results = build_recovery_stage_audit(
            parent_claim_id=recovered.parent_claim_id,
            claim=recovered.record.claim,
            child_ordinal=child_ordinal,
            recovery_action=recovery.recovery_action,
            admission_route=recovered.admission_route,
            target_expression=enrichment.get("target_numeric_expression"),
        )
        context_slots = enrichment.get("context_enriched_slots", [])
        provenance = {
            str(slot): "CONTEXT"
            for slot in context_slots
            if isinstance(slot, str)
        }
        slot_audit = audit_claim_slots(recovered.record.claim, provenance=provenance)
        entries.append(
            PipelineEntry(
                recovered.parent_claim_id,
                recovered.record.claim,
                recovery.recovery_action,
                recovered.admission_route,
                status,
                reason,
                recovered.official_resolution,
                lineage_record=lineage,
                stage_results=stage_results,
                slot_audit=slot_audit,
            )
        )
    return entries


def _verify_stored_claim(
    record: ClaimRegistryRecord,
    official_service: OfficialEvidenceResolver,
) -> PipelineEntry:
    """Use persisted slots without sending source or context to an extractor."""
    claim = record.claim
    decision = classify_admissibility(
        claim.parse_reason,
        "AUTO" if claim.parse_status == "AUTO_OK" else "HOLD",
    )
    route = {
        "VERIFIABLE": "KOSIS_PIPELINE_ELIGIBLE",
        "MULTI_CLAIM_SPLIT_REQUIRED": "MULTI_CLAIM_SPLIT_REQUIRED",
        "CONTEXT_REQUIRED": "CONTEXT_REQUIRED",
        "STRUCTURAL_HOLD": "STRUCTURAL_HOLD",
    }[decision.route]
    resolution = (
        official_service.resolve(claim, article_date=record.article_published_at)
        if route == "KOSIS_PIPELINE_ELIGIBLE" and record.article_published_at is not None
        else None
    )
    status, reason = _terminal_result(resolution, route, record.article_published_at, claim)
    lineage, stage_results = build_recovery_stage_audit(
        parent_claim_id=claim.claim_id,
        claim=claim,
        child_ordinal=1,
        recovery_action="NO_RECOVERY",
        admission_route=route,
    )
    slot_audit = audit_claim_slots(claim)
    return PipelineEntry(
        claim.claim_id,
        claim,
        "DIRECT" if route == "KOSIS_PIPELINE_ELIGIBLE" else "NO_RECOVERY",
        route,
        status,
        reason,
        resolution,
        lineage_record=lineage,
        stage_results=stage_results,
        slot_audit=slot_audit,
    )

def _terminal_result(
    resolution: Any | None,
    admission_route: str,
    article_published_at: date | None,
    claim: ClaimSchema,
) -> tuple[str, str | None]:
    if resolution is not None:
        verdict = getattr(resolution, "verdict", None)
        if verdict is None and isinstance(resolution, dict):
            return str(resolution.get("route_status") or "HOLD"), resolution.get("reason_code")
        return str(getattr(verdict, "route_status", "HOLD")), getattr(verdict, "reason_code", None)
    if article_published_at is None and admission_route == "KOSIS_PIPELINE_ELIGIBLE":
        return "HUMAN_REVIEW", "ARTICLE_DATE_REQUIRED"
    if admission_route != "KOSIS_PIPELINE_ELIGIBLE":
        return "HUMAN_REVIEW", claim.parse_reason or admission_route
    return "HUMAN_REVIEW", "OFFICIAL_RESOLUTION_NOT_ATTEMPTED"


def _article_id(article_text: str) -> str:
    return f"article_{sha256(article_text.strip().encode('utf-8')).hexdigest()[:16]}"
