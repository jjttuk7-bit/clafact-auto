"""Deterministic semantic compatibility between Claim indicators and units."""

from __future__ import annotations

from dataclasses import dataclass
import re

from schemas.claim_registry import ClaimRegistryRecord


@dataclass(frozen=True, slots=True)
class IndicatorUnitDecision:
    status: str
    reason_code: str
    indicator_family: str
    unit_family: str
    expected_unit_families: tuple[str, ...]
    suggested_indicator: str = ""


_EXPECTED = {
    "PERSON": ("PERSON",),
    "CURRENCY": ("CURRENCY",),
    "RATE": ("PERCENT",),
    "QUANTITY": ("MASS", "VEHICLE"),
    "HOUSEHOLD": ("HOUSEHOLD",),
    "AREA": ("AREA",),
    "DEPENDENCY_RATIO": ("PERSON", "PERCENT"),
    "PERSON_OR_RATE": ("PERSON", "PERCENT"),
}
_PIPELINE_BLOCK = {
    "INDICATOR_REFINEMENT_REQUIRED": "INDICATOR_REFINEMENT_REQUIRED",
    "INDICATOR_UNIT_CONFLICT": "INDICATOR_UNIT_MEASURE_MISMATCH",
    "REVIEW_REQUIRED": "INDICATOR_MEASURE_FAMILY_AMBIGUOUS",
}


def assess_indicator_unit(
    indicator: str,
    unit: str,
    target_role: str,
) -> IndicatorUnitDecision:
    """Classify one source-grounded indicator/unit pair without KOSIS access."""

    indicator_family = _indicator_family(indicator)
    unit_family = _unit_family(unit)
    role = re.sub(r"\s+", "", target_role or "")
    expected = _EXPECTED.get(indicator_family, ())

    if not indicator_family or not unit_family:
        return _decision(
            "REVIEW_REQUIRED",
            "INDICATOR_MEASURE_FAMILY_AMBIGUOUS",
            indicator_family or "UNKNOWN",
            unit_family or "UNKNOWN",
            expected,
        )
    if indicator_family == "COMPOSITE_GDP":
        if unit_family == "CURRENCY":
            return _compatible(indicator_family, unit_family, ("CURRENCY", "PERCENT"))
        if unit_family == "PERCENT" and role == "증감값":
            return _refinement(
                indicator,
                indicator_family,
                unit_family,
                ("CURRENCY", "PERCENT"),
                "GDP 성장률",
            )
        if unit_family == "PERCENT_POINT":
            return _refinement(
                indicator,
                indicator_family,
                unit_family,
                ("CURRENCY", "PERCENT"),
                "GDP 성장기여도",
            )
        if unit_family == "PERCENT":
            return _decision(
                "REVIEW_REQUIRED",
                "INDICATOR_MEASURE_FAMILY_AMBIGUOUS",
                indicator_family,
                unit_family,
                ("CURRENCY", "PERCENT"),
            )
        return _conflict(indicator_family, unit_family, ("CURRENCY", "PERCENT"))
    if indicator_family == "INDEX":
        if unit_family in {"PERCENT", "PERCENT_POINT"}:
            suffix = "변동률" if unit_family == "PERCENT" else "변동폭"
            return _refinement(
                indicator,
                indicator_family,
                unit_family,
                ("INDEX_POINT",),
                f"{indicator} {suffix}",
            )
        return _conflict(indicator_family, unit_family, ("INDEX_POINT",))
    if indicator_family == "COMPOSITE":
        if unit_family in {"PERCENT", "PERCENT_POINT"}:
            suffix = "증감률" if unit_family == "PERCENT" else "증감폭"
            return _refinement(
                indicator,
                indicator_family,
                unit_family,
                (),
                f"{indicator} {suffix}",
            )
        if "건설투자" in indicator and unit_family == "DWELLING":
            return _refinement(indicator, indicator_family, unit_family, (), "아파트 분양실적")
        return _conflict(indicator_family, unit_family, ())
    if indicator_family == "UNKNOWN":
        return _decision(
            "REVIEW_REQUIRED",
            "INDICATOR_MEASURE_FAMILY_AMBIGUOUS",
            indicator_family,
            unit_family,
            expected,
        )
    if unit_family in expected:
        return _compatible(indicator_family, unit_family, expected)
    if unit_family == "PERCENT":
        if indicator_family == "RATE":
            return _compatible(indicator_family, unit_family, expected)
        return _refinement(
            indicator,
            indicator_family,
            unit_family,
            expected,
            f"{indicator} 증감률" if role == "증감값" else f"{indicator} 비율",
        )
    if unit_family == "PERCENT_POINT":
        if indicator_family == "RATE" and role == "증감값":
            return _compatible(indicator_family, unit_family, ("PERCENT", "PERCENT_POINT"))
        if indicator_family == "RATE" or role == "증감값":
            return _refinement(
                indicator,
                indicator_family,
                unit_family,
                expected,
                f"{indicator} 증감폭",
            )
        if indicator_family == "CURRENCY":
            return _refinement(
                indicator,
                indicator_family,
                unit_family,
                expected,
                f"{indicator} 성장기여도",
            )
        return _conflict(indicator_family, unit_family, expected)
    if indicator_family == "CURRENCY" and unit_family in {"VEHICLE", "MASS"}:
        suggested = _trade_quantity_indicator(indicator, unit_family)
        return _refinement(
            indicator,
            indicator_family,
            unit_family,
            expected,
            suggested,
        )
    return _conflict(indicator_family, unit_family, expected)


def indicator_unit_preverification_reason(
    record: ClaimRegistryRecord,
) -> str | None:
    """Return a stable pre-KOSIS reason from persisted compatibility status."""

    enrichment = record.slot_enrichment or {}
    status = str(enrichment.get("indicator_unit_status") or "")
    return _PIPELINE_BLOCK.get(status)


def _indicator_family(indicator: str) -> str:
    compact = re.sub(r"[\s·/_()-]+", "", indicator or "").casefold()
    if not compact:
        return ""
    if "면적" in compact:
        return "AREA"
    if "가구" in compact or compact == "농가수":
        return "HOUSEHOLD"
    if any(token in compact for token in ("수출량", "수입량", "생산량")):
        return "QUANTITY"
    if any(token in compact for token in ("수출액", "수입액", "무역수지", "해외건설", "1인당gdp")):
        return "CURRENCY"
    if compact == "gdp":
        return "COMPOSITE_GDP"
    if "부양비" in compact:
        return "DEPENDENCY_RATIO"
    if "규모비율" in compact:
        return "PERSON_OR_RATE"
    if any(token in compact for token in ("률", "비율", "부양비")):
        return "RATE"
    if "지수" in compact:
        return "INDEX"
    if any(token in compact for token in ("인구", "취업자", "출생아", "사망자", "경제활동인구")):
        return "PERSON"
    if any(token in compact for token in ("건설투자", "산업생산", "광공업생산")):
        return "COMPOSITE"
    return "UNKNOWN"


def _unit_family(unit: str) -> str:
    compact = re.sub(r"\s+", "", unit or "").casefold()
    if compact in {"%", "퍼센트"}:
        return "PERCENT"
    if compact in {"%p", "%포인트", "퍼센트포인트", "％p", "％포인트"}:
        return "PERCENT_POINT"
    if compact in {"명", "천명", "만명"}:
        return "PERSON"
    if compact in {"원", "만원", "억원", "조원", "달러", "만달러", "억달러", "십억달러", "엔", "유로", "usd", "천불"}:
        return "CURRENCY"
    if compact in {"대"}:
        return "VEHICLE"
    if compact in {"톤", "t", "kg", "㎏"}:
        return "MASS"
    if compact in {"ha", "헥타르", "㎡", "km²", "㎢"}:
        return "AREA"
    if compact == "가구":
        return "HOUSEHOLD"
    if compact == "호":
        return "DWELLING"
    if compact == "건":
        return "CASE"
    if compact == "곳":
        return "PLACE"
    if compact in {"개", "개사", "개국", "채", "채널"}:
        return "COUNT"
    return ""


def _decision(status: str, reason: str, indicator_family: str, unit_family: str, expected: tuple[str, ...], suggested: str = "") -> IndicatorUnitDecision:
    return IndicatorUnitDecision(status, reason, indicator_family, unit_family, expected, suggested)


def _compatible(indicator_family: str, unit_family: str, expected: tuple[str, ...]) -> IndicatorUnitDecision:
    return _decision("COMPATIBLE", "INDICATOR_UNIT_COMPATIBLE", indicator_family, unit_family, expected)


def _refinement(indicator: str, indicator_family: str, unit_family: str, expected: tuple[str, ...], suggested: str) -> IndicatorUnitDecision:
    return _decision("INDICATOR_REFINEMENT_REQUIRED", "INDICATOR_VARIANT_REQUIRED", indicator_family, unit_family, expected, suggested or indicator)


def _conflict(indicator_family: str, unit_family: str, expected: tuple[str, ...]) -> IndicatorUnitDecision:
    return _decision("INDICATOR_UNIT_CONFLICT", "INDICATOR_UNIT_MEASURE_MISMATCH", indicator_family, unit_family, expected)


def _trade_quantity_indicator(indicator: str, unit_family: str) -> str:
    if "수출액" in indicator:
        return indicator.replace("수출액", "수출대수" if unit_family == "VEHICLE" else "수출량")
    if "수입액" in indicator:
        return indicator.replace("수입액", "수입대수" if unit_family == "VEHICLE" else "수입량")
    return indicator
