"""Target-aware multi-Claim recovery followed by shared official verification."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import cast

from core.admission_recovery import AdmissionRoute, OfficialEvidenceResolver, RecoveryAction, RecoveryEntry, RecoveryResult
from core.admission_recovery_v2 import recover_registry_record_v2
from core.claim_admissibility import classify_admissibility
from core.claim_group_recovery import build_grouping_hold
from core.claim_group_normalizer import (
    build_source_anchored_grouping_plan,
    normalize_grouping_plan,
)
from core.claim_group_validator import validate_grouping_plan
from core.claim_parser import StructuredClaimExtractor, parse_claim
from core.operational_error import OperationalStageError, run_operational_stage
from core.record_comparison_splitter import split_record_comparison_claim
from core.targeted_claim_splitter import (
    TargetedClaimInput,
    build_targeted_claim_inputs,
    discover_numeric_mentions,
)
from core.trade_claim_recovery import recover_trade_period, split_trade_composite_claim
from core.source_target_grounding import trusted_target_expression
from core.validated_claim_recovery import recover_validated_claim
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.claim_group import ClaimGroupingPlan


class _StaticExtractor:
    def __init__(self, claim: ClaimSchema): self.claim = claim
    def extract(self, source_sentence: str, **kwargs) -> ClaimSchema: return self.claim


def recover_registry_record_v3(record: ClaimRegistryRecord, *, extractor: StructuredClaimExtractor, official_service: OfficialEvidenceResolver, article_context: str | None = None) -> RecoveryResult:
    """Split targets, then use article context only as a controlled second pass."""
    trade_recovered = recover_trade_period(record.claim, record.article_published_at)
    if trade_recovered != record.claim:
        trade_recovered = recover_validated_claim(
            trade_recovered, record.article_published_at,
            source_value_text=record.claim.source_sentence,
        )
        record = record.model_copy(update={"claim": trade_recovered})
    trade_children = split_trade_composite_claim(record.claim, record.article_published_at)
    if len(trade_children) > 1:
        return _recover_trade_children(record, trade_children, official_service)
    record_children = split_record_comparison_claim(record.claim)
    if len(record_children) > 1:
        return _recover_record_children(record, record_children, official_service)
    prelinked_target = trusted_target_expression(record)
    if prelinked_target is not None:
        return _recover_prelinked_target(
            record,
            prelinked_target,
            extractor=extractor,
            official_service=official_service,
            article_context=article_context,
        )
    mentions = discover_numeric_mentions(record.claim.source_sentence)
    grouper = getattr(extractor, "group_claims", None)
    target_roles: list[dict[str, str]]
    target_role_assignments: list[list[dict[str, str]]]
    grouping_source_fallback = False
    if len(mentions) >= 2 and callable(grouper):
        try:
            plan = run_operational_stage(
                "CLAIM_SPLIT",
                lambda: grouper(record.claim.source_sentence, mentions),
            )
        except OperationalStageError:
            plan = build_source_anchored_grouping_plan(
                record.claim.source_sentence, mentions
            )
            if plan is None:
                raise
            grouping_source_fallback = True
        if not isinstance(plan, ClaimGroupingPlan):
            raise TypeError("Structured grouper must return ClaimGroupingPlan")
        plan = normalize_grouping_plan(record.claim.source_sentence, mentions, plan)
        validation = validate_grouping_plan(mentions, plan)
        if not validation.valid:
            return build_grouping_hold(
                record,
                mentions=mentions,
                reason_code=validation.reason_code or "GROUPING_AMBIGUOUS",
            )
        targets = []
        target_roles = []
        target_role_assignments = []
        for group in validation.groups:
            numeric_roles = dict(group.numeric_roles)
            payload = {
                "source_sentence": record.claim.source_sentence,
                "target_numeric_expression": group.main_expression,
                "supporting_numeric_expressions": [
                    {"expression": expression, "role": role}
                    for expression, role in group.numeric_roles
                    if role != "MAIN_VALUE"
                ],
                "instruction": (
                    "중심 수치와 같은 Claim에 속한 비교·증감 수치를 함께 사용해 "
                    "독립 Claim 하나만 12슬롯으로 구조화"
                ),
            }
            targets.append(
                TargetedClaimInput(
                    group.main_expression,
                    json.dumps(payload, ensure_ascii=False),
                )
            )
            target_roles.append(numeric_roles)
            target_role_assignments.append([
                {
                    "mention_id": mention_id,
                    "expression": expression,
                    "role": role,
                }
                for mention_id, expression, role in group.numeric_assignments
            ])
    else:
        targets = build_targeted_claim_inputs(record.claim.source_sentence)
        target_roles = [{} for _ in targets]
        target_role_assignments = [[] for _ in targets]
    if not targets:
        return recover_registry_record_v2(record, extractor=extractor, official_service=official_service, article_context=article_context)
    entries: list[RecoveryEntry] = []
    for target, numeric_roles, numeric_role_assignments in zip(
        targets, target_roles, target_role_assignments, strict=True
    ):
        parsed = _parse_target(target.expression, target.extractor_input, extractor, record)
        parsed_before_context = parsed
        context_used = False
        if _should_retry_with_context(parsed) and article_context:
            payload = json.loads(target.extractor_input)
            payload["article_context"] = article_context
            payload["target_already_split"] = True
            payload["target_split_instruction"] = (
                "The target_numeric_expression is already one separate child Claim. "
                "Do not HOLD it only because the source sentence has other numbers."
            )
            payload["instruction"] = "부족한 지역·시점·대상만 본문으로 보강하고 target_numeric_expression 하나만 12슬롯 구조화"
            parsed = _parse_target(target.expression, json.dumps(payload, ensure_ascii=False), extractor, record)
            context_used = True
        context_enriched_slots = _changed_slots(parsed_before_context, parsed) if context_used else []
        parsed = parsed.model_copy(update={"claim_id": _child_id(record.claim.source_sentence, target.expression), "source_sentence": record.claim.source_sentence})
        parsed = recover_validated_claim(parsed, record.article_published_at, source_value_text=target.expression)
        route = _admission_route(parsed)
        derived = record.model_copy(update={"claim": parsed, "source_ref": "admission_recovery_v3", "slot_enrichment": {
            "stage": "TARGETED_MULTI_CLAIM_SPLIT", "parent_claim_id": record.claim.claim_id,
            "target_numeric_expression": target.expression, "admission_route": route,
            "numeric_roles": numeric_roles,
            "numeric_role_assignments": numeric_role_assignments,
            "source_ref": record.source_ref, "article_context_used": context_used,
            "context_enriched_slots": context_enriched_slots,
            "grouping_source_fallback": grouping_source_fallback,
        }})
        resolution = official_service.resolve(parsed, article_date=record.article_published_at) if route == "KOSIS_PIPELINE_ELIGIBLE" and record.article_published_at is not None else None
        entries.append(RecoveryEntry(record.claim.claim_id, derived, route, resolution))
    return RecoveryResult(cast(RecoveryAction, "MULTI_CLAIM_SPLIT"), entries)


def _recover_prelinked_target(
    record: ClaimRegistryRecord,
    expression: str,
    *,
    extractor: StructuredClaimExtractor,
    official_service: OfficialEvidenceResolver,
    article_context: str | None,
) -> RecoveryResult:
    """Recover exactly one previously span-verified numeric target."""

    payload = {
        "source_sentence": record.claim.source_sentence,
        "target_numeric_expression": expression,
        "instruction": "원문에서 확정된 target_numeric_expression 하나만 12슬롯 구조화",
    }
    encoded = json.dumps(payload, ensure_ascii=False)
    parsed = _parse_target(expression, encoded, extractor, record)
    parsed_before_context = parsed
    context_used = False
    if _should_retry_with_context(parsed) and article_context:
        payload["article_context"] = article_context
        payload["target_already_split"] = True
        payload["instruction"] = (
            "확정된 target_numeric_expression은 바꾸지 말고 부족한 문맥 슬롯만 보강"
        )
        parsed = _parse_target(
            expression,
            json.dumps(payload, ensure_ascii=False),
            extractor,
            record,
        )
        context_used = True
    parsed = parsed.model_copy(update={
        "claim_id": _child_id(record.claim.source_sentence, expression),
        "source_sentence": record.claim.source_sentence,
    })
    parsed = recover_validated_claim(
        parsed,
        record.article_published_at,
        source_value_text=expression,
    )
    route = _admission_route(parsed)
    enrichment = dict(record.slot_enrichment or {})
    enrichment.update({
        "stage": "PRELINKED_SOURCE_TARGET",
        "parent_claim_id": record.claim.claim_id,
        "target_numeric_expression": expression,
        "admission_route": route,
        "source_ref": record.source_ref,
        "article_context_used": context_used,
        "context_enriched_slots": (
            _changed_slots(parsed_before_context, parsed) if context_used else []
        ),
    })
    derived = record.model_copy(update={
        "claim": parsed,
        "source_ref": "admission_recovery_v3",
        "slot_enrichment": enrichment,
    })
    resolution = (
        official_service.resolve(parsed, article_date=record.article_published_at)
        if route == "KOSIS_PIPELINE_ELIGIBLE" and record.article_published_at is not None
        else None
    )
    return RecoveryResult(
        cast(
            RecoveryAction, "CONTEXT_REPARSE" if context_used else "DIRECT"
        ),
        [RecoveryEntry(record.claim.claim_id, derived, route, resolution)],
    )


def _recover_trade_children(
    parent: ClaimRegistryRecord,
    children: list[ClaimSchema],
    official_service: OfficialEvidenceResolver,
) -> RecoveryResult:
    entries: list[RecoveryEntry] = []
    for child in children:
        child = recover_validated_claim(child, parent.article_published_at)
        route = _admission_route(child)
        derived = parent.model_copy(update={
            "claim": child,
            "source_ref": "admission_recovery_v3",
            "slot_enrichment": {
                "stage": "TRADE_TOTAL_COUNTRY_SHARE_SPLIT",
                "parent_claim_id": parent.claim.claim_id,
                "trade_child_role": (child.condition or {}).get("trade_claim_role"),
                "admission_route": route,
                "source_ref": parent.source_ref,
            },
        })
        resolution = (
            official_service.resolve(child, article_date=parent.article_published_at)
            if route == "KOSIS_PIPELINE_ELIGIBLE" and parent.article_published_at is not None
            else None
        )
        entries.append(RecoveryEntry(parent.claim.claim_id, derived, route, resolution))
    return RecoveryResult(cast(RecoveryAction, "MULTI_CLAIM_SPLIT"), entries)


def _recover_record_children(
    parent: ClaimRegistryRecord,
    children: list[ClaimSchema],
    official_service: OfficialEvidenceResolver,
) -> RecoveryResult:
    entries: list[RecoveryEntry] = []
    for child in children:
        child = recover_validated_claim(
            child, parent.article_published_at, source_value_text=parent.claim.source_sentence
        )
        route = _admission_route(child)
        derived = parent.model_copy(update={
            "claim": child,
            "source_ref": "admission_recovery_v3",
            "slot_enrichment": {
                "stage": "RECORD_COMPARISON_SPLIT",
                "parent_claim_id": parent.claim.claim_id,
                "record_child_type": child.calculation,
                "admission_route": route,
                "source_ref": parent.source_ref,
            },
        })
        resolution = official_service.resolve(child, article_date=parent.article_published_at) if route == "KOSIS_PIPELINE_ELIGIBLE" and parent.article_published_at is not None else None
        entries.append(RecoveryEntry(parent.claim.claim_id, derived, route, resolution))
    return RecoveryResult(cast(RecoveryAction, "RECORD_COMPARISON_SPLIT"), entries)


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
