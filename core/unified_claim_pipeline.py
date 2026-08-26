"""Single Article/Registry orchestration path for Admission recovery and KOSIS evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
from typing import Any

from core.admission_recovery import OfficialEvidenceResolver
from core.admission_recovery_v3 import recover_registry_record_v3
from core.claim_context_guard import context_target_unresolved
from core.direct_value_child_guard import (
    apply_direct_value_child_guard,
    enrich_target_qualifiers_from_context,
)
from core.claim_admissibility import classify_admissibility
from core.article_claim_pipeline import parse_article_claims
from core.claim_lineage import ClaimLineageRecord
from core.indicator_unit_compatibility import indicator_unit_preverification_reason
from core.claim_parser import StructuredClaimExtractor
from core.operational_error import OperationalStageError, run_operational_stage
from core.recovery_stage_audit import build_recovery_stage_audit
from core.trade_claim_recovery import split_trade_composite_claim
from core.validated_claim_recovery import recover_validated_claim
from core.slot_audit import audit_claim_slots
from core.source_target_grounding import (
    repair_exact_target_grounding,
    target_link_preverification_reason,
    trusted_target_expression,
)
from core.source_sign_direction import (
    apply_source_sign_direction_enrichment,
    sign_direction_preverification_reason,
)
from core.targeted_claim_splitter import discover_numeric_mentions
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
    record = repair_exact_target_grounding(record)
    context_target = trusted_target_expression(record)
    if context_target is not None and article_context:
        context_claim = enrich_target_qualifiers_from_context(
            record.claim,
            target_expression=context_target,
            article_context=article_context,
        )
        record = record.model_copy(update={"claim": context_claim})

    target_link_reason = target_link_preverification_reason(record)
    if target_link_reason is not None:
        held_claim = record.claim.model_copy(update={
            "parse_status": "HUMAN_REVIEW",
            "parse_reason": target_link_reason,
        })
        return [
            _verify_stored_claim(
                record.model_copy(update={"claim": held_claim}), official_service
            )
        ]
    target_expression = trusted_target_expression(record)
    if (
        target_expression is not None
        and not _multi_claim_grouping_required(record, extractor)
    ):
        recovered_claim = recover_validated_claim(
            record.claim,
            record.article_published_at,
            source_value_text=target_expression,
        )
        guarded_claim = apply_direct_value_child_guard(
            recovered_claim,
            target_expression=target_expression,
        )
        record = record.model_copy(update={"claim": guarded_claim})
        if guarded_claim.parse_status != "AUTO_OK":
            return [_verify_stored_claim(record, official_service)]
    indicator_unit_reason = indicator_unit_preverification_reason(record)
    if (
        indicator_unit_reason is not None
        and not _multi_claim_grouping_required(record, extractor)
    ):
        held_claim = record.claim.model_copy(update={
            "parse_status": "HUMAN_REVIEW",
            "parse_reason": indicator_unit_reason,
        })
        return [
            _verify_stored_claim(
                record.model_copy(update={"claim": held_claim}), official_service
            )
        ]
    sign_direction_reason = sign_direction_preverification_reason(record)
    if (
        sign_direction_reason is not None
        and not _multi_claim_grouping_required(record, extractor)
    ):
        held_claim = record.claim.model_copy(update={
            "parse_status": "HUMAN_REVIEW",
            "parse_reason": sign_direction_reason,
        })
        return [
            _verify_stored_claim(
                record.model_copy(update={"claim": held_claim}), official_service
            )
        ]
    record = apply_source_sign_direction_enrichment(record)
    if _sentence_only_context_target_unresolved(record, article_context):
        held_claim = record.claim.model_copy(update={
            "parse_status": "HOLD",
            "parse_reason": "CONTEXT_TARGET_UNRESOLVED",
        })
        held_record = record.model_copy(update={"claim": held_claim})
        return [_verify_stored_claim(held_record, official_service)]

    try:
        if allow_structured_recovery:
            recovery = recover_registry_record_v3(
                record,
                extractor=extractor,
                official_service=official_service,
                article_context=article_context,
            )
        else:
            return _verify_deterministic_stored_claims(record, official_service)
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


def _verify_deterministic_stored_claims(
    record: ClaimRegistryRecord,
    official_service: OfficialEvidenceResolver,
) -> list[PipelineEntry]:
    children = split_trade_composite_claim(record.claim, record.article_published_at)
    split = len(children) > 1
    entries: list[PipelineEntry] = []
    source_value_text = trusted_target_expression(record)
    for child in children:
        recovered = recover_validated_claim(
            child,
            record.article_published_at,
            source_value_text=source_value_text,
        )
        entry = _verify_stored_claim(record.model_copy(update={"claim": recovered}), official_service)
        if split:
            entry = replace(
                entry,
                parent_claim_id=record.claim.claim_id,
                recovery_action="MULTI_CLAIM_SPLIT",
            )
        entries.append(entry)
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


def _multi_claim_grouping_required(
    record: ClaimRegistryRecord,
    extractor: StructuredClaimExtractor,
) -> bool:
    return len(discover_numeric_mentions(record.claim.source_sentence)) >= 2 and callable(
        getattr(extractor, "group_claims", None)
    )


def _sentence_only_context_target_unresolved(
    record: ClaimRegistryRecord,
    article_context: str | None,
) -> bool:
    if not article_context:
        return False
    source = "".join(record.claim.source_sentence.split())
    context = "".join(article_context.split())
    if source != context:
        return False
    return context_target_unresolved(record.claim.source_sentence, record.claim)


def _article_id(article_text: str) -> str:
    return f"article_{sha256(article_text.strip().encode('utf-8')).hexdigest()[:16]}"
