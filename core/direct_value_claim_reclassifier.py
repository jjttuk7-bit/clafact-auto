"""General, source-grounded reclassification for type-8 direct-value Claims."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from core.direct_value_verification_type import classify_direct_value_target
from core.source_numeric_inventory import inventory_numeric_mentions
from core.source_numeric_role_classifier import classify_numeric_roles
from core.source_observation_guard import observation_preverification_reason
from schemas.claim import ClaimSchema


_MOVE_BY_CALCULATION = {
    "DIFFERENCE": ("MOVE_CHANGE_AMOUNT", "6.증감량", "CALCULATION_DIFFERENCE"),
    "GROWTH_RATE": ("MOVE_CHANGE_RATE", "7.증감률", "CALCULATION_GROWTH_RATE"),
    "SHARE": ("MOVE_SHARE", "4.비중·구성비", "CALCULATION_SHARE"),
    "RECORD_HIGH": ("MOVE_RECORD", "5.최고·최저", "CALCULATION_RECORD"),
    "RECORD_LOW": ("MOVE_RECORD", "5.최고·최저", "CALCULATION_RECORD"),
    "RANK": ("MOVE_RANK", "순위", "CALCULATION_RANK"),
}
_MOVE_BY_TYPE = {
    "DIFFERENCE": ("MOVE_CHANGE_AMOUNT", "6.증감량", "SOURCE_CHANGE_AMOUNT"),
    "GROWTH_RATE": ("MOVE_CHANGE_RATE", "7.증감률", "SOURCE_CHANGE_RATE"),
    "SHARE": ("MOVE_SHARE", "4.비중·구성비", "SOURCE_SHARE"),
    "RECORD": ("MOVE_RECORD", "5.최고·최저", "SOURCE_RECORD"),
    "RANK": ("MOVE_RANK", "순위", "SOURCE_RANK"),
}
_EXCLUSION_CODES = {
    "NON_OBSERVED_FORECAST": "EXCLUDE_FORECAST",
    "NON_STATISTICAL_POLICY_THRESHOLD": "EXCLUDE_POLICY_THRESHOLD",
    "NON_STATISTICAL_PRIVATE_TRANSACTION": "EXCLUDE_PRIVATE_TRANSACTION",
    "NON_STATISTICAL_PRODUCT_PRICE": "EXCLUDE_PRODUCT_PRICE",
}


@dataclass(frozen=True, slots=True)
class DirectValueReclassification:
    claim_id: str
    top_level_result: str
    result_code: str
    target_tab: str
    applied_rule: str
    source_evidence: str
    original_reason: str
    final_reason: str
    split_set: str


def reclassify_direct_value_claim(row: Mapping[str, object]) -> DirectValueReclassification:
    """Classify by source numeric role and verification method, never Claim ID."""

    claim_id = _text(row, "자식Claim번호") or _text(row, "원본부모Claim번호")
    source = _text(row, "원문")
    indicator = _text(row, "지표")
    unit = _text(row, "단위")
    calculation = _text(row, "계산방식") or "DIRECT_VALUE"
    original_reason = _text(row, "개선후사유")
    split_set = _text(row, "사용집합")
    value = _float_or_none(row.get("기사값"))
    claim = ClaimSchema(
        claim_id=claim_id,
        source_sentence=source,
        indicator=indicator or None,
        value=value,
        unit=unit or None,
        time=_text(row, "기준시점") or None,
        frequency=_text(row, "주기") or None,
        calculation=calculation,
        parse_status="AUTO_OK",
    )

    excluded_reason = observation_preverification_reason(claim)
    if excluded_reason:
        return _decision(claim_id, "EXCLUDE_FROM_KOSIS", _EXCLUSION_CODES[excluded_reason], "검증 제외", excluded_reason, "", original_reason, excluded_reason, split_set)

    configured_move = _MOVE_BY_CALCULATION.get(calculation)
    if configured_move:
        code, tab, rule = configured_move
        return _decision(claim_id, "MOVE_TO_OTHER_TYPE", code, tab, rule, _text(row, "대상수치표현"), original_reason, rule, split_set)

    mentions = inventory_numeric_mentions(source)
    roles = classify_numeric_roles(
        source_sentence=source,
        mentions=mentions,
        claim_value=value,
        claim_unit=unit,
        indicator=indicator,
    )
    selected = [item for item in roles.assignments if item.auto_target_eligible]
    expression = _text(row, "대상수치표현")
    if expression and expression not in source:
        expression = ""
    if len(selected) == 1:
        expression = selected[0].expression

    if expression:
        type_decision = classify_direct_value_target(source, target_expression=expression, unit=unit, indicator=indicator)
        move = _MOVE_BY_TYPE.get(type_decision.type_code)
        if move:
            code, tab, rule = move
            return _decision(claim_id, "MOVE_TO_OTHER_TYPE", code, tab, rule, expression, original_reason, type_decision.reason_code or rule, split_set)
        if roles.target_status == "TARGET_SELECTED" and _required_slots_present(claim):
            return _decision(claim_id, "KEEP_DIRECT_VALUE", "KEEP_DIRECT_RECOVERED", "8.직접값", "SOURCE_GROUNDED_DIRECT_VALUE", expression, original_reason, "SOURCE_GROUNDED_DIRECT_VALUE", split_set)

    if original_reason == "DIRECT_VALUE_CHANGE_TARGET_MISCLASSIFIED":
        is_rate = unit.replace(" ", "") in {"%", "％", "퍼센트"}
        return _decision(claim_id, "MOVE_TO_OTHER_TYPE", "MOVE_CHANGE_RATE" if is_rate else "MOVE_CHANGE_AMOUNT", "7.증감률" if is_rate else "6.증감량", "PARSE_REASON_CHANGE_TARGET", expression, original_reason, "RECLASSIFY_CHANGE_TARGET", split_set)

    final_reason = original_reason or roles.target_status or "CLAIM_STRUCTURE_RECOVERY_REQUIRED"
    return _decision(claim_id, "KEEP_DIRECT_VALUE", "KEEP_DIRECT_REQUIRES_RECOVERY", "8.직접값", "FAIL_CLOSED_SLOT_RECOVERY", expression, original_reason, final_reason, split_set)


def _required_slots_present(claim: ClaimSchema) -> bool:
    return all((claim.indicator, claim.value is not None, claim.unit, claim.time))


def _decision(claim_id: str, top: str, code: str, tab: str, rule: str, evidence: str, original_reason: str, final_reason: str, split_set: str) -> DirectValueReclassification:
    return DirectValueReclassification(claim_id, top, code, tab, rule, evidence, original_reason, final_reason, split_set)


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value).strip()


def _float_or_none(value: object) -> float | None:
    text = "" if value is None else str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
