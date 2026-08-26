"""Fail-closed checks for source qualifiers on direct-value child Claims."""

from __future__ import annotations

import json
import re

from core.direct_value_verification_type import (
    _find_target_span,
    classify_direct_value_target,
)
from schemas.claim import ClaimSchema


_QUALIFIERS = (
    "건설업", "제조업", "농림어업", "도소매업", "숙박음식점업",
    "운수창고업", "금융보험업", "서비스업",
    "대졸 이상", "고졸", "중졸 이하",
)
_CHANGE_AFTER_TARGET = re.compile(
    r"^(?:\s|[은는이가을를로으로]){0,5}(?:늘|줄|증가|감소|상승|하락|개선|악화)"
)


def direct_value_child_preverification_reason(
    claim: ClaimSchema,
    *,
    target_expression: str,
    target_role: str | None = None,
) -> str | None:
    """Reject a direct child before KOSIS when source semantics were lost."""

    if claim.calculation not in {None, "DIRECT_VALUE", "THRESHOLD"}:
        return None
    if target_role == "CHANGE_VALUE":
        return "DIRECT_VALUE_CHANGE_TARGET_MISCLASSIFIED"
    source = claim.source_sentence
    type_decision = classify_direct_value_target(
        source,
        target_expression=target_expression,
        unit=claim.unit,
        indicator=claim.indicator,
    )
    if type_decision.reason_code is not None:
        return type_decision.reason_code
    span = _find_target_span(source, target_expression)
    if span is None:
        return "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE"
    start, end = span
    tail = source[end:end + 16]
    if _CHANGE_AFTER_TARGET.search(tail):
        return "DIRECT_VALUE_CHANGE_TARGET_MISCLASSIFIED"

    local = _target_clause(source, start, end - start)
    slots = _slot_text(claim)
    for qualifier in _QUALIFIERS:
        if qualifier in local and qualifier not in slots:
            return f"SOURCE_TARGET_DIMENSION_MISSING:{qualifier}"
    return None


def apply_direct_value_child_guard(
    claim: ClaimSchema,
    *,
    target_expression: str,
    target_role: str | None = None,
) -> ClaimSchema:
    decision = classify_direct_value_target(
        claim.source_sentence,
        target_expression=target_expression,
        unit=claim.unit,
        indicator=claim.indicator,
    )
    reason = direct_value_child_preverification_reason(
        claim,
        target_expression=target_expression,
        target_role=target_role,
    )
    if reason is None:
        if decision.type_code == "THRESHOLD":
            operator = _threshold_operator(
                claim.source_sentence,
                target_expression,
            )
            if operator is None:
                return claim.model_copy(update={
                    "parse_status": "HUMAN_REVIEW",
                    "parse_reason": "THRESHOLD_OPERATOR_UNRESOLVED",
                })
            return claim.model_copy(update={
                "calculation": "THRESHOLD",
                "condition": {
                    "operator": operator,
                    "threshold_value": str(claim.value),
                    "threshold_unit": claim.unit,
                },
                "parse_status": "AUTO_OK",
                "parse_reason": None,
            })
        if decision.type_code == "DIRECT_VALUE" and claim.calculation == "THRESHOLD":
            return claim.model_copy(update={
                "calculation": "DIRECT_VALUE",
                "condition": None,
                "parse_status": "AUTO_OK",
                "parse_reason": None,
            })
        return claim
    return claim.model_copy(update={
        "parse_status": "HUMAN_REVIEW",
        "parse_reason": reason,
    })


def _target_clause(source: str, start: int, expression_length: int) -> str:
    left = max(0, start - 40)
    prefix = source[left:start]
    separators = ("반면,", "반면", "한편,", "한편", ";", "。", ".", ",")
    boundary = max((prefix.rfind(value) + len(value) for value in separators), default=0)
    return source[left + boundary:start + expression_length]

def _slot_text(claim: ClaimSchema) -> str:
    values: list[object] = [
        claim.indicator,
        claim.population,
        claim.region,
        claim.dimension,
    ]
    return " ".join(
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        if isinstance(value, dict)
        else str(value or "")
        for value in values
    )


def _threshold_operator(source: str, expression: str) -> str | None:
    start = source.find(expression)
    if start < 0:
        return None
    tail = source[start + len(expression):start + len(expression) + 32]
    if re.search(r"(?:이상|넘(?:었|어|는|어서)|초과|돌파)", tail):
        return "GTE" if "이상" in tail else "GT"
    if re.search(r"(?:이하|밑돌|못\s*미치|아래로)", tail):
        return "LTE"
    if "미만" in tail:
        return "LT"
    return None