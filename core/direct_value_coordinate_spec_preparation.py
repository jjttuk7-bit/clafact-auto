"""Prepare one unresolved direct-value Claim for official coordinate discovery."""

from __future__ import annotations

from dataclasses import dataclass

from core.direct_value_child_guard import apply_direct_value_child_guard
from core.indicator_unit_compatibility import indicator_unit_preverification_reason
from core.kosis_query_spec_compiler import compile_kosis_query_spec
from core.source_indicator_refinement import apply_source_indicator_refinement
from core.source_observation_guard import observation_preverification_reason
from core.source_sign_direction import (
    apply_source_sign_direction_enrichment,
    sign_direction_preverification_reason,
)
from core.source_target_grounding import (
    repair_exact_target_grounding,
    target_link_preverification_reason,
    trusted_target_expression,
)
from core.validated_claim_recovery import recover_validated_claim
from schemas.claim_registry import ClaimRegistryRecord
from schemas.kosis_query_spec import KosisQuerySpecSchema


@dataclass(frozen=True, slots=True)
class PreparedCoordinateSpec:
    record: ClaimRegistryRecord
    spec: KosisQuerySpecSchema
    target_expression: str | None


def prepare_coordinate_spec(record: ClaimRegistryRecord) -> PreparedCoordinateSpec:
    """Apply the unified pipeline's deterministic pre-KOSIS guards once."""

    prepared = repair_exact_target_grounding(record)
    expression = trusted_target_expression(prepared)
    reasons: list[str] = []
    link_reason = target_link_preverification_reason(prepared)
    if link_reason:
        reasons.append(link_reason)
    elif expression is None:
        reasons.append("TARGET_NOT_SOURCE_GROUNDED")

    if expression is not None:
        recovered = recover_validated_claim(
            prepared.claim,
            prepared.article_published_at,
            source_value_text=expression,
        )
        guarded = apply_direct_value_child_guard(
            recovered,
            target_expression=expression,
            target_role=str(
                (prepared.slot_enrichment or {}).get("target_numeric_role") or ""
            ),
        )
        prepared = prepared.model_copy(update={"claim": guarded})
        if guarded.parse_status == "AUTO_OK":
            prepared = apply_source_indicator_refinement(
                prepared,
                target_expression=expression,
            )

    for reason in (
        observation_preverification_reason(prepared.claim),
        indicator_unit_preverification_reason(prepared),
        sign_direction_preverification_reason(prepared),
    ):
        if reason:
            reasons.append(reason)
    prepared = apply_source_sign_direction_enrichment(prepared)

    if prepared.claim.parse_status != "AUTO_OK":
        reasons.append(prepared.claim.parse_reason or "CLAIM_PARSE_UNCERTAIN")

    spec = compile_kosis_query_spec(
        prepared.claim,
        article_date=prepared.article_published_at,
    )
    reasons.extend(spec.readiness_reasons)
    reasons = list(dict.fromkeys(reason for reason in reasons if reason))
    if reasons:
        spec = spec.model_copy(update={
            "readiness_status": "PRE_VERIFICATION",
            "readiness_reasons": reasons,
        })
    return PreparedCoordinateSpec(prepared, spec, expression)
