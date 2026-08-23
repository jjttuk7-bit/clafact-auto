"""Conservatively classify what should happen before official verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.slot_audit import audit_claim_slots
from core.targeted_claim_splitter import build_targeted_claim_inputs
from schemas.claim import ClaimSchema


ClaimDisposition = Literal[
    "OFFICIAL_VERIFICATION_TARGET",
    "FORECAST_OR_POLICY",
    "NO_VERIFIABLE_NUMERIC_ASSERTION",
    "SOURCE_CONTEXT_INSUFFICIENT",
]
NextRoute = Literal[
    "OFFICIAL_SEARCH",
    "PRE_VERIFICATION_EXCLUDE",
    "CONTEXT_REVIEW",
]


@dataclass(frozen=True, slots=True)
class ClaimDispositionDecision:
    disposition: ClaimDisposition
    reason_code: str
    next_route: NextRoute


_FORECAST_OR_POLICY_MARKERS = (
    "전망",
    "예상",
    "내다봤",
    "방침",
    "계획",
    "예정",
    "공약",
    "가능성",
    "대응한다",
)


def classify_claim_disposition(claim: ClaimSchema) -> ClaimDispositionDecision:
    """Return a pre-verification disposition without inventing official evidence."""

    source = claim.source_sentence.strip()
    if any(marker in source for marker in _FORECAST_OR_POLICY_MARKERS):
        return ClaimDispositionDecision(
            "FORECAST_OR_POLICY",
            "EXPLICIT_FORECAST_OR_POLICY_MARKER",
            "PRE_VERIFICATION_EXCLUDE",
        )

    audit = audit_claim_slots(claim)
    if audit.eligible_for_official_search:
        return ClaimDispositionDecision(
            "OFFICIAL_VERIFICATION_TARGET",
            "TWELVE_SLOT_COMPLETE",
            "OFFICIAL_SEARCH",
        )

    targets = build_targeted_claim_inputs(source)
    if claim.value is None and not targets:
        return ClaimDispositionDecision(
            "NO_VERIFIABLE_NUMERIC_ASSERTION",
            "NO_STATISTICAL_TARGET_VALUE",
            "PRE_VERIFICATION_EXCLUDE",
        )

    reason = next(iter(audit.reason_codes), None) or claim.parse_reason
    return ClaimDispositionDecision(
        "SOURCE_CONTEXT_INSUFFICIENT",
        reason or "SOURCE_CONTEXT_INSUFFICIENT",
        "CONTEXT_REVIEW",
    )
