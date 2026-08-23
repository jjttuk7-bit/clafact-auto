"""Target-aware multi-Claim recovery followed by shared official verification."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import cast

from core.admission_recovery import AdmissionRoute, OfficialEvidenceResolver, RecoveryAction, RecoveryEntry, RecoveryResult
from core.admission_recovery_v2 import recover_registry_record_v2
from core.claim_admissibility import classify_admissibility
from core.claim_parser import StructuredClaimExtractor, parse_claim
from core.operational_error import run_operational_stage
from core.targeted_claim_splitter import build_targeted_claim_inputs
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _StaticExtractor:
    def __init__(self, claim: ClaimSchema): self.claim = claim
    def extract(self, source_sentence: str, **kwargs) -> ClaimSchema: return self.claim


def recover_registry_record_v3(record: ClaimRegistryRecord, *, extractor: StructuredClaimExtractor, official_service: OfficialEvidenceResolver, article_context: str | None = None) -> RecoveryResult:
    """Split targets, then use article context only as a controlled second pass."""
    targets = build_targeted_claim_inputs(record.claim.source_sentence)
    if not targets:
        return recover_registry_record_v2(record, extractor=extractor, official_service=official_service, article_context=article_context)
    entries: list[RecoveryEntry] = []
    for target in targets:
        parsed = _parse_target(target.expression, target.extractor_input, extractor, record)
        parsed_before_context = parsed
        context_used = False
        if _should_retry_with_context(parsed) and article_context:
            payload = json.loads(target.extractor_input)
            payload["article_context"] = article_context
            payload["instruction"] = "부족한 지역·시점·대상만 본문으로 보강하고 target_numeric_expression 하나만 12슬롯 구조화"
            parsed = _parse_target(target.expression, json.dumps(payload, ensure_ascii=False), extractor, record)
            context_used = True
        context_enriched_slots = _changed_slots(parsed_before_context, parsed) if context_used else []
        parsed = parsed.model_copy(update={"claim_id": _child_id(record.claim.source_sentence, target.expression), "source_sentence": record.claim.source_sentence})
        route = _admission_route(parsed)
        derived = record.model_copy(update={"claim": parsed, "source_ref": "admission_recovery_v3", "slot_enrichment": {
            "stage": "TARGETED_MULTI_CLAIM_SPLIT", "parent_claim_id": record.claim.claim_id,
            "target_numeric_expression": target.expression, "admission_route": route,
            "source_ref": record.source_ref, "article_context_used": context_used,
            "context_enriched_slots": context_enriched_slots,
        }})
        resolution = official_service.resolve(parsed, article_date=record.article_published_at) if route == "KOSIS_PIPELINE_ELIGIBLE" and record.article_published_at is not None else None
        entries.append(RecoveryEntry(record.claim.claim_id, derived, route, resolution))
    return RecoveryResult(cast(RecoveryAction, "MULTI_CLAIM_SPLIT"), entries)


def _parse_target(expression: str, extractor_input: str, extractor: StructuredClaimExtractor, record: ClaimRegistryRecord) -> ClaimSchema:
    extracted = run_operational_stage(
        "CLAIM_PARSE",
        lambda: extractor.extract(extractor_input, article_published_at=record.article_published_at),
    )
    if not isinstance(extracted, ClaimSchema):
        raise TypeError("Structured extractor must return ClaimSchema")
    return parse_claim(expression, _StaticExtractor(extracted), article_published_at=record.article_published_at)


def _admission_route(claim: ClaimSchema) -> AdmissionRoute:
    decision = classify_admissibility(claim.parse_reason, "AUTO" if claim.parse_status == "AUTO_OK" else "HOLD")
    if decision.route == "VERIFIABLE": return "KOSIS_PIPELINE_ELIGIBLE"
    if decision.route == "CONTEXT_REQUIRED": return "CONTEXT_REQUIRED"
    return "STRUCTURAL_HOLD"


def _should_retry_with_context(claim: ClaimSchema) -> bool:
    if _admission_route(claim) == "CONTEXT_REQUIRED":
        return True
    prefix = "MISSING_REQUIRED_SLOTS:"
    reason = (claim.parse_reason or "").strip()
    if not reason.startswith(prefix):
        return False
    missing_slots = {
        slot.strip() for slot in reason[len(prefix):].split(",") if slot.strip()
    }
    return bool(missing_slots) and missing_slots <= {"time"}


def _child_id(source_sentence: str, expression: str) -> str:
    digest = sha256((source_sentence + "\n" + expression).encode("utf-8")).hexdigest()[:16]
    return f"claim_{digest}"


def _changed_slots(before: ClaimSchema, after: ClaimSchema) -> list[str]:
    """Return only 12-slot values that article context actually populated or changed."""

    slot_names = (
        "indicator", "value", "unit", "time", "frequency", "region",
        "population", "dimension", "comparison", "calculation", "condition",
        "source_hint",
    )
    return [
        name
        for name in slot_names
        if getattr(before, name) != getattr(after, name)
        and getattr(after, name) not in (None, "")
    ]
