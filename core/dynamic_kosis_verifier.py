"""KOSIS verification for structured Claims."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
import re
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
from schemas.verdict import OfficialValueProvenanceSchema, VerdictSchema


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

    Candidate metadata and the official value API determine whether the Claim can be auto-verified.
    """
    recorder = VerificationTraceRecorder(claim.claim_id).claim_parsed()
    if concept.status != "MATCHED":
        reason = "CONCEPT_NOT_FOUND"
        recorder.concept_held(reason)
        return _hold(claim, recorder, reason, "No semantic standard matches the Claim context.")
    recorder.concept_mapped().catalog_searched()
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
    eligible_candidates = _prefer_exact_concept_code(concept, eligible_candidates)
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

    calculation_type = claim.calculation or "DIRECT_VALUE"
    evidence_cells = _calculation_cells(cell, claim, calculation_type)
    if evidence_cells is None:
        recorder.evidence_held("MISSING_COMPARISON_FOR_GROWTH_RATE")
        return _hold(
            claim, recorder, "MISSING_COMPARISON_FOR_GROWTH_RATE",
            "The comparison period is not explicit enough to resolve official evidence.", evidence_cells=[cell],
        )

    recorder.evidence_confirmed()
    official_values: list[float] = []
    provenance: list[OfficialValueProvenanceSchema] = []
    batch_fetch = getattr(official_fetcher, "fetch_many", None)
    try:
        fetched_values = (
            batch_fetch(evidence_cells, article_date=article_date)
            if callable(batch_fetch)
            else [
                official_fetcher.fetch(item, article_date=article_date)
                for item in evidence_cells
            ]
        )
    except Exception:
        recorder.official_value_held("FETCH_FAILED")
        return _hold(
            claim, recorder, "FETCH_FAILED", "Official value fetch failed.",
            evidence_cells=evidence_cells,
        )
    for evidence_cell, official_value in zip(evidence_cells, fetched_values, strict=True):
        if official_value.status != "SUCCESS" or official_value.value is None:
            recorder.official_value_held(official_value.status)
            return _hold(
                claim, recorder, official_value.status, "Official value is unavailable.", evidence_cells=evidence_cells,
            )
        official_values.append(official_value.value)
        provenance.append(
            OfficialValueProvenanceSchema(
                evidence_key=evidence_cell.canonical_key,
                source=official_value.source,
                content_hash=official_value.snapshot_hash,
            )
        )

    recorder.official_value_fetched()
    calculated = calculate(
        CalculationPlan(calculation_type=calculation_type, required_cells=evidence_cells), official_values
    )
    recorder.calculation_completed()
    if calculation_type == "DIFFERENCE" and _is_percentage_point_unit(claim.unit):
        claim_unit_value = _direction_checked_difference(calculated, claim)
    elif calculation_type in {"GROWTH_RATE", "SHARE"}:
        claim_unit_value = calculated
    else:
        claim_unit_value = convert_value(calculated, cell.unit or "", claim.unit or "")
    verdict = make_verdict(
        claim.claim_id, claim.value, official_values, claim_unit_value, tolerance=_claim_tolerance(claim)
    )
    recorder.verdict_completed()
    return attach_trace(
        verdict.model_copy(
            update={
                "evidence_cells": evidence_cells,
                "official_value_provenance": provenance,
            }
        ),
        recorder.build(),
    )


def _prefer_exact_concept_code(
    concept: StandardConceptSchema,
    candidates: list[KosisCandidateSchema],
) -> list[KosisCandidateSchema]:
    """Narrow ties only when official metadata contains the Concept's exact code."""
    concept_codes = {
        token
        for value in (concept.concept_id, concept.standard_key)
        if ":" in value
        if (token := value.rsplit(":", 1)[-1].strip())
    }
    if not concept_codes:
        return candidates
    exact = [
        candidate
        for candidate in candidates
        if concept_codes.intersection(
            str(code).strip()
            for member_codes in candidate.dimension_member_codes.values()
            for code in member_codes.values()
        )
    ]
    return exact



def _is_percentage_point_unit(unit: str | None) -> bool:
    return "".join((unit or "").split()).casefold() in {"%p", "%포인트", "퍼센트포인트"}


def _direction_checked_difference(calculated: float, claim: ClaimSchema) -> float:
    direction = ((claim.condition or {}).get("direction") or "").strip().upper()
    actual_direction = "INCREASE" if calculated > 0 else "DECREASE"
    return abs(calculated) if direction == actual_direction else -abs(calculated)


def _calculation_cells(
    cell: EvidenceCellSchema, claim: ClaimSchema, calculation_type: str
) -> list[EvidenceCellSchema] | None:
    if calculation_type == "DIRECT_VALUE":
        return [cell]
    if calculation_type not in {"GROWTH_RATE", "DIFFERENCE"}:
        return None
    comparison = _comparison_type(claim.comparison)
    comparison_period = _comparison_period(cell.prd_de, comparison)
    if comparison_period is None:
        return None
    comparison_cell = cell.model_copy(update={
        "prd_de": comparison_period,
        "canonical_key": cell.canonical_key.replace(f"PRD_DE={cell.prd_de}", f"PRD_DE={comparison_period}"),
    })
    return [cell, comparison_cell]


def _comparison_type(comparison: dict[str, str] | None) -> str | None:
    for value in (comparison or {}).values():
        normalized = re.sub(r"[\s_-]+", "", value).casefold()
        if normalized in {
            "yearoveryear", "전년대비", "전년동월대비", "전년동월비", "전년비", "전년",
        }:
            return "YEAR_OVER_YEAR"
        if normalized in {"monthovermonth", "전월대비", "전월비", "전월"}:
            return "MONTH_OVER_MONTH"
        if normalized in {"quarteroverquarter", "전분기대비", "전분기비", "전분기"}:
            return "QUARTER_OVER_QUARTER"
    return None


def _comparison_period(period: str, comparison: str | None) -> str | None:
    monthly = re.fullmatch(r"(\d{4})-(\d{2})", period)
    annual = re.fullmatch(r"\d{4}", period)
    quarterly = re.fullmatch(r"(\d{4})-Q([1-4])", period, re.IGNORECASE)
    if comparison == "YEAR_OVER_YEAR":
        if monthly:
            return f"{int(monthly.group(1)) - 1:04d}-{monthly.group(2)}"
        if annual:
            return f"{int(period) - 1:04d}"
        if quarterly:
            return f"{int(quarterly.group(1)) - 1:04d}-Q{quarterly.group(2)}"
    if comparison == "QUARTER_OVER_QUARTER" and quarterly:
        year, quarter = int(quarterly.group(1)), int(quarterly.group(2))
        previous_year, previous_quarter = (year - 1, 4) if quarter == 1 else (year, quarter - 1)
        return f"{previous_year:04d}-Q{previous_quarter}"
    if comparison == "MONTH_OVER_MONTH" and monthly:
        year, month = int(monthly.group(1)), int(monthly.group(2))
        previous_year, previous_month = (year - 1, 12) if month == 1 else (year, month - 1)
        return f"{previous_year:04d}-{previous_month:02d}"
    return None
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
