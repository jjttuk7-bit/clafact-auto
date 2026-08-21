"""Classify a parsed Claim by whether supplied source text can enter KOSIS verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AdmissibilityRoute = Literal[
    "VERIFIABLE",
    "STRUCTURAL_HOLD",
    "CONTEXT_REQUIRED",
    "MULTI_CLAIM_SPLIT_REQUIRED",
]


@dataclass(frozen=True)
class AdmissibilityDecision:
    route: AdmissibilityRoute
    reason_code: str


_DOWNSTREAM_REASONS = {
    "NO_EVIDENCE_COORDINATE_CANDIDATE",
    "NO_HARD_GUARD_CANDIDATE",
    "AMBIGUOUS_MARGIN",
    "LOW_SEMANTIC_SCORE",
    "CONCEPT_NOT_FOUND",
    "NO_DATA",
    "AS_OF_UNAVAILABLE",
    "PUBLICATION_FETCH_FAILED",
    "MISSING_COMPARISON_FOR_GROWTH_RATE",
    "OUTSIDE_TOLERANCE",
}
_RELATIVE_TIME_MARKERS = ("지난달", "지난해", "작년", "재작년", "올해", "이달", "이번", "내년", "새해", "올 들어", "최근")
_FORECAST_MARKERS = ("전망", "예상", "조건부", "공약", "계획", "예정", "가능성", "추정")
_MULTI_CLAIM_MARKERS = ("복수", "여러", "두 개", "두 가지", "함께 제시", "단일", "복합", "각각")
_RANGE_MARKERS = ("범위", "안팎", "가량", "대", "~", "넘게", "가까이", "이상", "미만")


def classify_admissibility(reason: str | None, route_status: str) -> AdmissibilityDecision:
    """Return a controlled routing decision without promoting parser HOLDs."""
    text = (reason or "").strip()
    if route_status == "AUTO" or any(text.startswith(code) for code in _DOWNSTREAM_REASONS):
        return AdmissibilityDecision("VERIFIABLE", "KOSIS_STAGE_REACHED")
    if text.startswith("MISSING_REQUIRED_SLOTS"):
        return AdmissibilityDecision("STRUCTURAL_HOLD", "MISSING_REQUIRED_SLOT")
    if text.startswith("MULTI_CLAIM_SPLIT_REQUIRED"):
        return AdmissibilityDecision(
            "MULTI_CLAIM_SPLIT_REQUIRED", "MULTI_CLAIM_SPLIT_REQUIRED"
        )
    if any(marker in text for marker in _RELATIVE_TIME_MARKERS):
        return AdmissibilityDecision("CONTEXT_REQUIRED", "RELATIVE_TIME_UNRESOLVED")
    if any(marker in text for marker in _FORECAST_MARKERS):
        return AdmissibilityDecision("STRUCTURAL_HOLD", "FORECAST_OR_CONDITIONAL")
    if any(marker in text for marker in _MULTI_CLAIM_MARKERS):
        return AdmissibilityDecision("STRUCTURAL_HOLD", "MULTI_CLAIM")
    if any(marker in text for marker in _RANGE_MARKERS):
        return AdmissibilityDecision("STRUCTURAL_HOLD", "RANGE_VALUE")
    if text.startswith("CLAIM_PARSE_UNCERTAIN"):
        return AdmissibilityDecision("CONTEXT_REQUIRED", "INDICATOR_UNRESOLVED")
    return AdmissibilityDecision("CONTEXT_REQUIRED", "SOURCE_CONTEXT_UNRESOLVED")
