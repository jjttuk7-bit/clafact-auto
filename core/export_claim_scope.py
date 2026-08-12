"""Deterministic scope gate for annual export growth Claims."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Literal

from schemas.claim import ClaimSchema

ExportScopeRoute = Literal[
    "NOT_APPLICABLE", "ANNUAL_TOTAL_YOY", "PARTIAL_PERIOD",
    "DIMENSION_SPECIFIC", "FORECAST", "SLOT_MISMATCH",
]


@dataclass(frozen=True, slots=True)
class ExportScopeDecision:
    route: ExportScopeRoute
    reason_code: str | None = None


_FORECAST_MARKERS = ("전망", "예상", "내다보", "것으로 봤", "것으로 보", "계획")
_PARTIAL_MARKERS = (
    "1~", "1∼", "1-", "1월", "2월", "3월", "4월", "5월", "6월",
    "7월", "8월", "9월", "10월", "11월", "12월", "지난달", "이달",
    "상반기", "하반기", "분기", "일평균", "하루 평균", "초순", "중순",
    "누계", "이 기간", "같은 기간", "전년 동기", "전년 동월",
)
_DIMENSION_MARKERS = (
    "대미", "대중", "대일", "미국 수출", "중국 수출", "일본 수출",
    "반도체", "자동차", "선박", "철강", "K푸드", "케이-푸드", "농식품",
    "신선식품", "친환경차", "하이브리드차", "품목별",
)
_ANNUAL_MARKERS = ("연간", "한 해", "지난해 수출", "작년 수출", "지난해 전체 수출", "작년 전체 수출")


def classify_export_claim_scope(
    claim: ClaimSchema, article_date: date | None,
) -> ExportScopeDecision:
    """Allow only unambiguous annual total-export year-over-year Claims."""
    if not _is_target_cluster(claim):
        return ExportScopeDecision("NOT_APPLICABLE")
    sentence = claim.source_sentence
    if any(marker in sentence for marker in _FORECAST_MARKERS):
        return ExportScopeDecision("FORECAST", "EXPORT_FORECAST_CLAIM")
    if claim.dimension or any(marker in sentence for marker in _DIMENSION_MARKERS):
        return ExportScopeDecision("DIMENSION_SPECIFIC", "EXPORT_DIMENSION_REQUIRED")
    if any(marker in sentence for marker in _PARTIAL_MARKERS):
        return ExportScopeDecision("PARTIAL_PERIOD", "EXPORT_PARTIAL_PERIOD")
    if not _is_year_over_year(claim):
        return ExportScopeDecision("SLOT_MISMATCH", "EXPORT_COMPARISON_REQUIRED")
    if not any(marker in sentence for marker in _ANNUAL_MARKERS):
        return ExportScopeDecision("SLOT_MISMATCH", "EXPORT_ANNUAL_SCOPE_UNCONFIRMED")
    if not _time_matches_sentence(claim, article_date):
        return ExportScopeDecision("SLOT_MISMATCH", "EXPORT_TIME_SLOT_MISMATCH")
    return ExportScopeDecision("ANNUAL_TOTAL_YOY")


def _is_target_cluster(claim: ClaimSchema) -> bool:
    frequency = re.sub(r"[\s_-]+", "", claim.frequency or "").casefold()
    return (
        claim.indicator == "수출액"
        and claim.calculation == "GROWTH_RATE"
        and frequency in {"y", "year", "yearly", "annual", "년", "연"}
    )


def _is_year_over_year(claim: ClaimSchema) -> bool:
    values = " ".join((claim.comparison or {}).values())
    normalized = re.sub(r"[\s_-]+", "", values).casefold()
    if any(token in normalized for token in ("yearoveryear", "전년대비", "전년동기", "전년동월", "1년전")):
        return True
    return any(token in claim.source_sentence for token in ("전년 대비", "전년보다", "1년 전", "1년전"))


def _time_matches_sentence(claim: ClaimSchema, article_date: date | None) -> bool:
    match = re.search(r"\d{4}", claim.time or "")
    if match is None:
        return False
    claim_year = int(match.group())
    sentence = claim.source_sentence
    if article_date and any(token in sentence for token in ("작년", "지난해")):
        return claim_year == article_date.year - 1
    explicit_years = [int(value) for value in re.findall(r"(?<!\d)(\d{4})년", sentence)]
    return not explicit_years or claim_year == explicit_years[0]
