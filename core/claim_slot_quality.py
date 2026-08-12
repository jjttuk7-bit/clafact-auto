"""Deterministic safety checks for imported 12-slot Claim quality."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Literal

from core.claim_dimensions import dimension_member_values, normalized_dimension_members
from core.unit_normalizer import compatible_units
from schemas.claim import ClaimSchema


@dataclass(frozen=True, slots=True)
class SlotQualityDecision:
    status: Literal["PASS", "HOLD"]
    reason_code: str | None = None
    detected_modifier: str | None = None


_TRADE_PRODUCT_MODIFIERS = (
    "자동차부품",
    "중고차",
    "자동차",
    "반도체",
    "철강",
    "의약품",
    "화장품",
    "농수산식품",
    "농수산물",
    "가공식품",
    "떡류",
)

_SPECIFIC_INFLATION_MODIFIERS = (
    "가공식품",
    "외식",
    "근원물가",
    "농산물 및 석유류 제외",
    "식료품·에너지 제외",
    "식료품 및 에너지 제외",
    "석유류",
    "개인 서비스",
    "공공서비스",
    "주택, 수도, 전기 및 연료",
    "식료품·비주류 음료",
    "의류 및 신발",
)


def assess_claim_slot_quality(claim: ClaimSchema) -> SlotQualityDecision:
    """Hold lossy 12-slot claims before KOSIS table selection."""
    indicator = _normalize(claim.indicator)
    source = _normalize(claim.source_sentence)
    if indicator == "수입액" and "수입차" in source and "등록" in source:
        return SlotQualityDecision(
            status="HOLD",
            reason_code="CLAIM_PARSE_UNCERTAIN",
            detected_modifier="수입차 등록 비율",
        )
    if indicator == "수출액":
        threshold_issue = _threshold_contract_issue(claim)
        if threshold_issue is not None:
            return SlotQualityDecision(
                status="HOLD",
                reason_code="CLAIM_PARSE_UNCERTAIN",
                detected_modifier=threshold_issue,
            )
        rank_issue = _rank_contract_issue(claim)
        if rank_issue is not None:
            return SlotQualityDecision(
                status="HOLD",
                reason_code="CLAIM_PARSE_UNCERTAIN",
                detected_modifier=rank_issue,
            )
        growth_issue = _growth_rate_contract_issue(claim)
        if growth_issue is not None:
            return SlotQualityDecision(
                status="HOLD",
                reason_code="CLAIM_PARSE_UNCERTAIN",
                detected_modifier=growth_issue,
            )
        difference_issue = _difference_contract_issue(claim)
        if difference_issue is not None:
            return SlotQualityDecision(
                status="HOLD",
                reason_code="CLAIM_PARSE_UNCERTAIN",
                detected_modifier=difference_issue,
            )
        if claim.calculation == "DIRECT_VALUE" and not _is_currency_unit(claim.unit):
            return SlotQualityDecision(
                status="HOLD",
                reason_code="CLAIM_PARSE_UNCERTAIN",
                detected_modifier=f"수출액/비화폐 단위 불일치:{claim.unit or '-'}",
            )
        if claim.calculation == "DIRECT_VALUE" and "기술수출액" in source:
            return SlotQualityDecision(
                status="HOLD",
                reason_code="CLAIM_PARSE_UNCERTAIN",
                detected_modifier="기술 수출액/상품 수출액 개념 불일치",
            )
        if claim.calculation == "DIRECT_VALUE" and not any(
            marker in source
            for marker in ("수출액", "수출금액", "수출규모", "수출실적", "수출은", "수출이")
        ):
            return SlotQualityDecision(
                status="HOLD",
                reason_code="CLAIM_PARSE_UNCERTAIN",
                detected_modifier="수출액 대상 표현 없음",
            )
        dimension_values = {_normalize(value) for value in dimension_member_values(claim.dimension)}
        if (
            "미국" in dimension_values
            and "우리나라수출" in source
            and "대미" in source
            and source.count("수출") >= 2
            and source.count("달러") >= 2
        ):
            return SlotQualityDecision(
                status="HOLD",
                reason_code="CLAIM_PARSE_UNCERTAIN",
                detected_modifier="국가 총수출/대미 수출 다중 대상",
            )
        for modifier in _TRADE_PRODUCT_MODIFIERS:
            normalized_modifier = _normalize(modifier)
            product_export_phrases = (
                f"{normalized_modifier}수출액",
                f"대미{normalized_modifier}수출액",
                f"{normalized_modifier}대미수출액",
            )
            if any(phrase in source for phrase in product_export_phrases) and not any(
                normalized_modifier in value for value in dimension_values
            ):
                return SlotQualityDecision(
                    status="HOLD",
                    reason_code="CLAIM_PARSE_UNCERTAIN",
                    detected_modifier=modifier,
                )
        return SlotQualityDecision(status="PASS")
    if indicator not in {"물가상승률", "물가상승율"}:
        return SlotQualityDecision(status="PASS")

    for modifier in _SPECIFIC_INFLATION_MODIFIERS:
        if _normalize(modifier) in source and _normalize(modifier) not in indicator:
            return SlotQualityDecision(
                status="HOLD",
                reason_code="CLAIM_PARSE_UNCERTAIN",
                detected_modifier=modifier,
            )
    return SlotQualityDecision(status="PASS")


def _difference_contract_issue(claim: ClaimSchema) -> str | None:
    if claim.calculation != "DIFFERENCE":
        return None
    comparison = claim.comparison or {}
    if not comparison:
        return "DIFFERENCE comparison 누락"
    current_text = (comparison.get("current_value") or "").strip()
    reference_text = (comparison.get("reference_value") or "").strip()
    if (not current_text or not reference_text) and comparison.get("claimed_operands"):
        return "DIFFERENCE current/reference 미분리"
    comparison_type = (comparison.get("type") or "").strip().upper()
    allowed_comparisons = {"YEAR_OVER_YEAR", "MONTH_OVER_MONTH", "QUARTER_OVER_QUARTER"}
    if comparison_type not in allowed_comparisons:
        return f"DIFFERENCE comparison.type 불일치:{comparison_type or '-'}"
    if not current_text:
        return "DIFFERENCE current_value 누락"
    if not reference_text:
        return "DIFFERENCE reference_value 누락"
    operand_unit = (comparison.get("operand_unit") or "").strip()
    if not operand_unit:
        return "DIFFERENCE operand_unit 누락"
    if not _difference_units_compatible(claim.unit, operand_unit):
        return f"DIFFERENCE 단위 불일치:{claim.unit or '-'}/{operand_unit}"
    try:
        current_value = float(current_text.replace(",", ""))
        reference_value = float(reference_text.replace(",", ""))
    except ValueError:
        return "DIFFERENCE current/reference 비수치"
    direction = ((claim.condition or {}).get("direction") or "").strip().upper()
    if not direction:
        return "DIFFERENCE direction 누락"
    if direction not in {"INCREASE", "DECREASE"}:
        return f"DIFFERENCE direction 불일치:{direction}"
    difference = current_value - reference_value
    magnitude = abs(difference)
    if claim.value is None or abs(abs(claim.value) - magnitude) > 1e-9:
        rendered_claim = "-" if claim.value is None else f"{claim.value:g}"
        return f"DIFFERENCE value 불일치:{rendered_claim}/{magnitude:g}"
    actual_direction = "INCREASE" if difference > 0 else "DECREASE"
    if direction != actual_direction:
        return f"DIFFERENCE direction/value 불일치:{direction}/{actual_direction}"
    return None


def _difference_units_compatible(claim_unit: str | None, operand_unit: str) -> bool:
    normalized_claim = _normalize(claim_unit)
    normalized_operand = _normalize(operand_unit)
    if normalized_claim in {"%p", "%포인트", "퍼센트포인트"}:
        return normalized_operand in {"%", "퍼센트"}
    return bool(claim_unit and compatible_units(claim_unit, operand_unit))


def _growth_rate_contract_issue(claim: ClaimSchema) -> str | None:
    if claim.calculation != "GROWTH_RATE":
        return None
    if not claim.unit or not compatible_units(claim.unit, "%"):
        return f"GROWTH_RATE 단위 불일치:{claim.unit or '-'}"
    comparison = claim.comparison or {}
    if not comparison:
        return "GROWTH_RATE comparison 누락"
    comparison_type = (comparison.get("type") or "").strip().upper()
    allowed_comparisons = {"YEAR_OVER_YEAR", "MONTH_OVER_MONTH", "QUARTER_OVER_QUARTER"}
    if comparison_type not in allowed_comparisons:
        rendered = comparison_type or "-"
        return f"GROWTH_RATE comparison.type 불일치:{rendered}"
    operand_values = _percentage_operand_values(comparison.get("claimed_operands"))
    if len(operand_values) >= 2:
        return f"GROWTH_RATE 다중 대상 미분리:{len(operand_values) + 1}"
    if operand_values and claim.value is not None and abs(operand_values[0] - claim.value) > 1e-9:
        return f"GROWTH_RATE target value 불일치:{claim.value}/{operand_values[0]}"
    direction = ((claim.condition or {}).get("direction") or "").strip().upper()
    if not direction:
        return "GROWTH_RATE direction 누락"
    if direction not in {"INCREASE", "DECREASE"}:
        return f"GROWTH_RATE direction 불일치:{direction}"
    return None


def _percentage_operand_values(raw: str | None) -> list[float]:
    if not raw:
        return []
    try:
        operands = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return []
    if not isinstance(operands, list):
        return []
    values: list[float] = []
    for operand in operands:
        if not isinstance(operand, dict) or not compatible_units(str(operand.get("unit", "")), "%"):
            continue
        try:
            values.append(float(operand["value"]))
        except (KeyError, TypeError, ValueError):
            continue
    return values


def _rank_contract_issue(claim: ClaimSchema) -> str | None:
    if claim.calculation != "RANK":
        return None
    if _normalize(claim.unit) != "위":
        return f"RANK 단위 불일치:{claim.unit or '-'}"
    if claim.value is None or claim.value <= 0 or not float(claim.value).is_integer():
        return f"RANK 순위 비정수:{claim.value}"
    dimensions = normalized_dimension_members(claim.dimension)
    product_values = next(
        (values for key, values in dimensions.items() if _normalize(key) in {"품목", "상품"}),
        [],
    )
    if not product_values:
        return "RANK 대상 품목 누락"
    if len(product_values) != 1:
        return f"RANK 대상 품목 복수:{len(product_values)}"
    condition = claim.condition or {}
    if not condition:
        return "RANK condition 누락"
    rank_value_text = (condition.get("rank_value") or "").strip()
    if not rank_value_text:
        return "RANK rank_value 누락"
    try:
        rank_value = float(rank_value_text.replace(",", ""))
    except ValueError:
        return "RANK rank_value 비수치"
    order = (condition.get("order") or "").strip().upper()
    if not order:
        return "RANK order 누락"
    if order not in {"DESC", "ASC"}:
        return f"RANK order 불일치:{order}"
    population_scope = (condition.get("population_scope") or "").strip()
    if not population_scope:
        return "RANK population_scope 누락"
    claim_rank = int(claim.value)
    if rank_value != claim_rank:
        rendered = int(rank_value) if rank_value.is_integer() else rank_value
        return f"RANK value 불일치:{claim_rank}/{rendered}"
    return None

def _threshold_contract_issue(claim: ClaimSchema) -> str | None:
    if claim.calculation != "THRESHOLD":
        return None
    condition = claim.condition or {}
    if not condition:
        return "THRESHOLD condition 누락"
    operator = (condition.get("operator") or "").strip().upper()
    if not operator:
        return "THRESHOLD operator 누락"
    if operator not in {"GT", "GTE", "LT", "LTE"}:
        return f"THRESHOLD operator 불일치:{operator}"
    threshold_value = (condition.get("threshold_value") or "").strip()
    if not threshold_value:
        return "THRESHOLD threshold_value 누락"
    try:
        float(threshold_value.replace(",", ""))
    except ValueError:
        return "THRESHOLD threshold_value 비수치"
    threshold_unit = (condition.get("threshold_unit") or "").strip()
    if not threshold_unit:
        return "THRESHOLD threshold_unit 누락"
    if not claim.unit or not compatible_units(claim.unit, threshold_unit):
        return f"THRESHOLD 단위 불일치:{claim.unit or '-'}/{threshold_unit}"
    return None

def _is_currency_unit(value: str | None) -> bool:
    normalized = _normalize(value)
    return normalized.endswith(("원", "달러", "불", "usd"))


def _normalize(value: str | None) -> str:
    return "".join((value or "").split()).casefold()
