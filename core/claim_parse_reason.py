"""Stable operational taxonomy for provider-authored Claim parse details."""

from __future__ import annotations

_ALLOWED_CODES = {
    "AMBIGUOUS_COMPARISON",
    "ARTICLE_DATE_REQUIRED",
    "ARTICLE_DATE_REQUIRED_FOR_RELATIVE_TIME",
    "CLAIM_REPARSE_FAILED",
    "EXTRACTION_FAILED",
    "FORECAST_CLAIM",
    "KOSIS_HALF_YEAR_PERIOD_UNSUPPORTED",
    "SLOT_AMBIGUOUS",
    "STRUCTURED_EXTRACTOR_NOT_CONFIGURED",
}
_ALLOWED_SLOT_NAMES = {
    "indicator", "value", "unit", "time", "frequency", "region",
    "population", "dimension", "comparison", "calculation", "condition",
    "source_hint",
}


def operational_parse_reason(detail: str | None) -> str:
    """Keep machine codes; collapse free-form explanations into stable queues."""
    text = (detail or "").strip()
    if text in _ALLOWED_CODES:
        return text
    if text.startswith("MISSING_REQUIRED_SLOTS:"):
        slot_names = [slot.strip() for slot in text.partition(":")[2].split(",")]
        if slot_names and all(slot in _ALLOWED_SLOT_NAMES for slot in slot_names):
            return "MISSING_REQUIRED_SLOTS:" + ",".join(sorted(set(slot_names)))
        return "CLAIM_PARSE_UNCERTAIN"
    compact = "".join(text.split()).casefold()
    if any(marker in compact for marker in (
        "여러독립", "복수의수치", "두개의독립", "두수치", "단일주장으로추출",
        "단일목표로추출", "단일타깃으로추출", "단일수치주장으로확정",
    )):
        return "MULTIPLE_CLAIMS"
    if any(marker in compact for marker in (
        "향후", "전망", "예측", "예상", "발생할수", "실제기록값이아니",
    )):
        return "FORECAST_CLAIM"
    if any(marker in compact for marker in (
        "비교기준", "비교기간", "성장률유형", "기준값", "reference",
    )):
        return "COMPARISON_UNCLEAR"
    if any(marker in compact for marker in (
        "목표시점", "대상시점", "기준시점", "시점이", "기간이명시",
        "시간을확정", "대상기간", "기준기간",
    )):
        return "TIME_UNCLEAR"
    if any(marker in compact for marker in (
        "구체적인수치가없", "수치가명시되지", "단일값으로", "범위로제시",
        "정확한단일수치가아니", "정량값을추출할수없",
    )):
        return "VALUE_UNCLEAR"
    return "CLAIM_PARSE_UNCERTAIN"
