"""Compile source-grounded Claims into reusable KOSIS search constraints."""

from __future__ import annotations

import re
from datetime import date

from core.claim_dimensions import normalized_dimension_members
from core.region_aliases import NATIONAL_REGION_ALIASES
from schemas.claim import ClaimSchema
from schemas.kosis_query_spec import KosisQuerySpecSchema


_LOCAL_TERMS = (
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
    "충북", "충남", "전북", "전남", "경북", "경남", "제주", "특별시", "광역시", "도",
)


def compile_kosis_query_spec(
    claim: ClaimSchema, *, article_date: date | None,
) -> KosisQuerySpecSchema:
    dimensions = normalized_dimension_members(claim.dimension)
    frequency = _frequency(claim.frequency, claim.time)
    reasons = []
    if not claim.indicator:
        reasons.append("MISSING_INDICATOR")
    if claim.value is None:
        reasons.append("MISSING_VALUE")
    if not claim.unit:
        reasons.append("MISSING_UNIT")
    if not claim.time:
        reasons.append("MISSING_TIME")
    if not frequency:
        reasons.append("MISSING_FREQUENCY")
    if claim.calculation not in {None, "DIRECT_VALUE", "THRESHOLD"}:
        reasons.append("UNSUPPORTED_DIRECT_CALCULATION")
    terms = _unique([
        claim.indicator or "",
        *(member for members in dimensions.values() for member in members),
        claim.population or "",
        claim.region or "",
    ])
    return KosisQuerySpecSchema(
        claim_id=claim.claim_id,
        indicator=claim.indicator,
        measure_family=_measure_family(claim.indicator or "", claim.unit or ""),
        value=claim.value,
        unit=claim.unit,
        unit_family=_unit_family(claim.unit or ""),
        scale=_unit_scale(claim.unit or ""),
        period=claim.time,
        frequency=frequency,
        period_mode=("UNRESOLVED" if not claim.time else "CUMULATIVE" if frequency == "누계" or "/" in claim.time else "SINGLE"),
        region=claim.region,
        geography_scope=_geography(claim.region, claim.source_sentence),
        population=claim.population,
        dimensions=dimensions,
        calculation=claim.calculation or "DIRECT_VALUE",
        required_evidence_cells=1,
        readiness_status="PRE_VERIFICATION" if reasons else "COORDINATE_READY",
        readiness_reasons=reasons,
        search_terms=terms,
    )


def _frequency(value: str | None, period: str | None) -> str | None:
    key = re.sub(r"\s+", "", value or "").casefold()
    mapped = {"m": "월", "month": "월", "monthly": "월", "월간": "월", "q": "분기", "quarter": "분기", "quarterly": "분기", "y": "년", "year": "년", "annual": "년", "yearly": "년", "연": "년", "연간": "년", "ytd": "누계", "누계": "누계"}.get(key)
    if mapped:
        return mapped
    text = period or ""
    if re.search(r"\d{4}[-.]\d{1,2}", text):
        return "월"
    if re.search(r"Q[1-4]|[1-4]분기", text, re.IGNORECASE):
        return "분기"
    if re.fullmatch(r"\d{4}", text):
        return "년"
    return value or None


def _measure_family(indicator: str, unit: str) -> str:
    compact = re.sub(r"\s+", "", indicator)
    family = _unit_family(unit)
    if "기여도" in compact:
        return "CONTRIBUTION"
    if any(term in compact for term in ("률", "비율", "증감률")):
        return "RATE"
    if any(term in compact for term in ("수출량", "수입량", "생산량", "등록대수")):
        return "QUANTITY"
    if any(term in compact for term in ("수출액", "수입액", "무역수지", "소득", "금액")):
        return "CURRENCY"
    if "지수" in compact:
        return "INDEX"
    if any(term in compact for term in ("인구", "취업자", "출생아", "사망자")):
        return "PERSON"
    return family or "UNKNOWN"


def _unit_family(unit: str) -> str:
    compact = re.sub(r"\s+", "", unit).casefold()
    if compact in {"명", "천명", "만명"}: return "PERSON"
    if compact in {"%", "퍼센트"}: return "PERCENT"
    if compact in {"%p", "%포인트", "퍼센트포인트"}: return "PERCENT_POINT"
    if compact in {"원", "만원", "억원", "조원", "달러", "천달러", "만달러", "억달러", "천불", "usd"}: return "CURRENCY"
    if compact in {"톤", "t", "kg", "㎏", "대", "개", "건"}: return "QUANTITY"
    if compact in {"ha", "헥타르", "㎡", "㎢", "km²"}: return "AREA"
    if "=100" in compact: return "INDEX_POINT"
    return "UNKNOWN"


def _unit_scale(unit: str) -> float:
    compact = re.sub(r"\s+", "", unit).casefold()
    return {"천명": 1_000.0, "만명": 10_000.0, "만원": 10_000.0, "억원": 100_000_000.0, "조원": 1_000_000_000_000.0, "천달러": 1_000.0, "천불": 1_000.0, "만달러": 10_000.0, "억달러": 100_000_000.0}.get(compact, 1.0)


def _geography(region: str | None, source: str) -> str:
    if not region or region in NATIONAL_REGION_ALIASES:
        return "NATIONAL"
    if any(term in region for term in _LOCAL_TERMS):
        return "LOCAL"
    return "COUNTRY" if region in source else "UNRESOLVED"


def _unique(values: list[str]) -> list[str]:
    result = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result
