"""Profile-free KOSIS verification for structured Claims."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol

from core.calculator import calculate
from core.hard_guard import apply_hard_guard
from core.claim_verification_service import VerificationTraceRecorder
from core.evidence_resolver import resolve_evidence_cell
from core.kosis_fetcher import KosisValue
from core.semantic_matcher import semantic_match
from core.unit_normalizer import convert_value
from core.verdict_engine import make_verdict
from core.verification_trace import attach_trace
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.evidence import CalculationPlan, EvidenceCellSchema
from schemas.verdict import VerdictSchema


class OfficialValueFetcher(Protocol):
    def fetch(self, cell: EvidenceCellSchema, *, article_date: date | None = None) -> KosisValue: ...


def verify_claim_against_kosis(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    candidates: Iterable[KosisCandidateSchema],
    *,
    article_date: date,
    official_fetcher: OfficialValueFetcher,
) -> VerdictSchema:
    """Verify one already-structured Claim through the normal KOSIS pipeline.

    Candidate metadata and the official value API, rather than a registered
    verification profile, determine whether the Claim can be auto-verified.
    """
    recorder = VerificationTraceRecorder(claim.claim_id).claim_parsed().concept_mapped().catalog_searched()
    guarded_candidates = [candidate for candidate in candidates if apply_hard_guard(claim, candidate).passed]
    if not guarded_candidates:
        reason = "NO_HARD_GUARD_CANDIDATE"
        recorder.hard_guard_held(reason)
        return _hold(claim, recorder, reason, "No KOSIS candidate satisfies required Claim slots.")

    resolved_cells = {
        candidate.tbl_id: resolve_evidence_cell(claim, candidate)
        for candidate in guarded_candidates
    }
    eligible_candidates = [
        candidate
        for candidate in guarded_candidates
        if resolved_cells[candidate.tbl_id].status == "CONFIRMED"
    ]
    matches = semantic_match(claim, eligible_candidates)
    if not matches:
        reason = "NO_EVIDENCE_COORDINATE_CANDIDATE"
        recorder.hard_guard_held(reason)
        return _hold(claim, recorder, reason, "No KOSIS candidate has a complete official coordinate.")

    best = matches[0]
    recorder.hard_guard_passed().semantic_matched(
        best.route_status,
        best.reason_code or "MATCH_ACCEPTED",
        best.top1_top2_margin,
    )
    selected = next(candidate for candidate in candidates if candidate.tbl_id == best.candidate_tbl_id)
    cell = resolve_evidence_cell(claim, selected)
    if best.route_status != "AUTO" or cell.status != "CONFIRMED":
        recorder.evidence_held(best.reason_code or "EVIDENCE_COORDINATE_UNRESOLVED")
        return _hold(
            claim,
            recorder,
            best.reason_code or "EVIDENCE_COORDINATE_UNRESOLVED",
            "KOSIS item or dimension coordinate is not confirmed.",
            evidence_cells=[cell],
        )

    recorder.evidence_confirmed()
    official_value = official_fetcher.fetch(cell, article_date=article_date)
    if official_value.status != "SUCCESS" or official_value.value is None:
        recorder.official_value_held(official_value.status)
        return _hold(claim, recorder, official_value.status, "Official value is unavailable.", evidence_cells=[cell])

    recorder.official_value_fetched()
    calculated = calculate(CalculationPlan(calculation_type="DIRECT_VALUE", required_cells=[cell]), [official_value.value])
    recorder.calculation_completed()
    claim_unit_value = convert_value(calculated, cell.unit or "", claim.unit or "")
    verdict = make_verdict(
        claim.claim_id,
        claim.value,
        [official_value.value],
        claim_unit_value,
        tolerance=_claim_tolerance(claim),
    )
    recorder.verdict_completed()
    return attach_trace(verdict.model_copy(update={"evidence_cells": [cell]}), recorder.build())


def _hold(
    claim: ClaimSchema,
    recorder: VerificationTraceRecorder,
    reason_code: str,
    explanation: str,
    *,
    evidence_cells: list[EvidenceCellSchema] | None = None,
) -> VerdictSchema:
    verdict = make_verdict(claim.claim_id, claim.value, [], None)
    return attach_trace(
        verdict.model_copy(update={"reason_code": reason_code, "explanation": explanation, "evidence_cells": evidence_cells or []}),
        recorder.build(),
    )


def _claim_tolerance(claim: ClaimSchema) -> float:
    """Accept only the explicit reporting precision present in the article text."""
    if claim.unit == "명" and "천" in claim.source_sentence:
        return 500.0
    return 0.01