"""Source-grounded refinement of overly broad statistical indicators."""

from __future__ import annotations

import re

from core.indicator_unit_compatibility import assess_indicator_unit
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


_CONTRIBUTION = re.compile(r"((?:순수출|수출입|내수|소비|투자|정부지출)(?:의)?\s*성장\s*기여도)")
_RESPONSE_RATE = re.compile(r"((?:[가-힣]+(?:총조사|조사))의?\s*(?:최종\s*)?응답률)")
_REGISTRATION_COUNT = re.compile(r"((?:수입\s*)?(?:승용차|자동차)\s*(?:신규\s*)?등록\s*대수)")
_EXPORT_MASS = re.compile(r"([가-힣]+)를\s*[\d,.]+(?:만|천)?(?:톤|t|kg|㎏)\s*수출")
_GDP_GROWTH = re.compile(r"(?:[가-힣]+(?:은|는)\s*)?(?:\d{1,2}분기[^,.]{0,20})?[\d.]+%\s*성장")
_YTD_MONTH_RANGE = re.compile(r"올해\s*1\s*[~～-]\s*(\d{1,2})월")
_COUNTRY_GROWTH = re.compile(
    r"([가-힣]+)(?:은|는)\s*"
    r"(?:\d{1,2}분기(?:\([^)]*\))?에?\s*)?[\d.]+%\s*성장"
)


def refine_source_indicator(
    claim: ClaimSchema,
    *,
    target_expression: str,
) -> ClaimSchema:
    """Return a general source-grounded indicator variant when unambiguous."""

    source = claim.source_sentence
    indicator = claim.indicator or ""
    unit = re.sub(r"\s+", "", claim.unit or "")
    refined = ""
    dimensions = dict(claim.dimension or {})

    contribution = _CONTRIBUTION.search(source)
    response = _RESPONSE_RATE.search(source)
    registration = _REGISTRATION_COUNT.search(source)
    exported_mass = _EXPORT_MASS.search(source)
    if contribution and unit in {"%", "퍼센트", "%p", "%포인트", "퍼센트포인트"}:
        refined = re.sub(r"\s+", " ", contribution.group(1).replace("의 성장", " 성장")).strip()
    elif response and unit in {"%", "퍼센트"}:
        refined = re.sub(r"\s+", " ", response.group(1).replace("조사의", "조사 ")).strip()
    elif registration and unit == "대":
        refined = re.sub(r"\s+", " ", registration.group(1)).strip()
    elif exported_mass and unit in {"톤", "t", "kg", "㎏"}:
        product = exported_mass.group(1)
        refined = f"{product} 수출량"
        dimensions = {key: value for key, value in dimensions.items() if key != "raw"}
        dimensions["product"] = product
        partner = re.search(r"([가-힣]+)에\s*" + re.escape(product) + r"를", source)
        if partner:
            dimensions["trade_partner"] = partner.group(1)
    elif "생활물가지수" in source and unit in {"%", "퍼센트"}:
        refined = "생활물가 상승률"
    elif (_COUNTRY_GROWTH.search(source) or re.search(r"(?:GDP|국내총생산|경제성장률)", indicator, re.IGNORECASE)) and unit in {"%", "퍼센트"}:
        refined = "경제성장률"
    elif "평균 관세율" in source and unit in {"%", "퍼센트"}:
        refined = "평균 관세율"
    elif re.search(r"(?:관세율|세율|관세)", source) and unit in {"%", "퍼센트"}:
        refined = "관세율"

    if not refined or refined == indicator:
        return claim
    return claim.model_copy(update={
        "indicator": refined,
        "dimension": dimensions or None,
    })


def apply_source_indicator_refinement(
    record: ClaimRegistryRecord,
    *,
    target_expression: str,
) -> ClaimRegistryRecord:
    """Refine source-explicit measure, time and region and refresh its audit."""

    original = record.claim
    refined = refine_source_indicator(original, target_expression=target_expression)
    updates: dict[str, object] = {}
    source = original.source_sentence

    month_range = _YTD_MONTH_RANGE.search(source)
    if month_range and record.article_published_at is not None and refined.indicator and any(token in refined.indicator for token in ("수출", "수입", "무역")):
        year = record.article_published_at.year
        end_month = int(month_range.group(1))
        if 1 <= end_month <= 12:
            updates["time"] = f"{year}-01/{year}-{end_month:02d}"
            updates["frequency"] = "YTD"

    country_growth = _COUNTRY_GROWTH.search(source)
    if refined.indicator == "경제성장률" and country_growth:
        country = country_growth.group(1)
        if country not in {"한국", "우리나라", "경제", "성장률"}:
            updates["region"] = country
            updates["dimension"] = None

    if updates:
        refined = refined.model_copy(update=updates)
    if refined == original:
        return record

    enrichment = dict(record.slot_enrichment or {})
    target_role = str(enrichment.get("target_numeric_role") or "")
    decision = assess_indicator_unit(refined.indicator or "", refined.unit or "", target_role)
    enrichment.update({
        "source_indicator_original": original.indicator,
        "source_indicator_refined": refined.indicator,
        "source_indicator_refinement_status": "SOURCE_EXPLICIT_MEASURE",
        "source_indicator_refinement_version": "1.1",
        "indicator_unit_status": decision.status,
        "indicator_unit_reason_code": decision.reason_code,
        "indicator_measure_family": decision.indicator_family,
        "unit_measure_family": decision.unit_family,
        "suggested_indicator": decision.suggested_indicator,
    })
    return record.model_copy(update={"claim": refined, "slot_enrichment": enrichment})
