"""KOSIS verification for structured Claims."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
import re
from typing import Protocol

from core.calculator import calculate
from core.calculation_planner import build_calculation_plan
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
from schemas.verdict import (
    OfficialPublicationProvenanceSchema,
    OfficialValueProvenanceSchema,
    VerdictSchema,
)


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
    selected = next(candidate for candidate in eligible_candidates if candidate.tbl_id == best.candidate_tbl_id)
    cell = resolve_evidence_cell(claim, selected)
    tie_selected = _resolve_direct_value_tie(
        claim, matches, eligible_candidates, resolved_cells, official_fetcher, article_date
    )
    if best.route_status != "AUTO" and tie_selected is not None:
        selected, cell = tie_selected
        recorder.hard_guard_passed().semantic_matched(
            "AUTO", "OFFICIAL_VALUE_EQUIVALENT", best.top1_top2_margin
        )
    else:
        recorder.hard_guard_passed().semantic_matched(
            best.route_status,
            best.reason_code or "MATCH_ACCEPTED",
            best.top1_top2_margin,
        )
    if (best.route_status != "AUTO" and tie_selected is None) or cell.status != "CONFIRMED":
        recorder.evidence_held(best.reason_code or "EVIDENCE_COORDINATE_UNRESOLVED")
        return _hold(
            claim,
            recorder,
            best.reason_code or "EVIDENCE_COORDINATE_UNRESOLVED",
            "KOSIS item or dimension coordinate is not confirmed.",
            evidence_cells=[cell],
        )
    calculation_type = claim.calculation or "DIRECT_VALUE"
    plan = build_calculation_plan(claim, cell, selected)
    if plan is None:
        recorder.evidence_held("CALCULATION_EVIDENCE_PLAN_UNRESOLVED")
        return _hold(
            claim, recorder, "CALCULATION_EVIDENCE_PLAN_UNRESOLVED",
            "Required official evidence operands are not explicit enough to resolve.", evidence_cells=[cell],
        )
    evidence_cells = plan.required_cells

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
        provenance.append(_value_provenance(evidence_cell, official_value))
        if official_value.status != "SUCCESS" or official_value.value is None:
            recorder.official_value_held(official_value.status)
            return _hold(
                claim, recorder, official_value.status, "Official value is unavailable.",
                evidence_cells=evidence_cells, official_value_provenance=provenance,
            )
        official_values.append(official_value.value)

    recorder.official_value_fetched()
    calculated = calculate(plan, [*official_values, *plan.literal_values])
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



def _resolve_direct_value_tie(
    claim: ClaimSchema,
    matches: list[object],
    candidates: list[KosisCandidateSchema],
    resolved_cells: dict[str, EvidenceCellSchema],
    official_fetcher: OfficialValueFetcher,
    article_date: date,
) -> tuple[KosisCandidateSchema, EvidenceCellSchema] | None:
    """Resolve direct-value ties only when official values and dates are identical."""
    if claim.calculation not in {None, "DIRECT_VALUE"} or len(matches) < 2:
        return None
    top_score = getattr(matches[0], "semantic_score", None)
    tied_ids = [getattr(match, "candidate_tbl_id") for match in matches if getattr(match, "semantic_score", None) == top_score]
    if len(tied_ids) < 2:
        return None
    by_table = {candidate.tbl_id: candidate for candidate in candidates}
    signatures: set[tuple[float, str | None, date]] = set()
    selected: tuple[KosisCandidateSchema, EvidenceCellSchema] | None = None
    for table_id in tied_ids:
        candidate = by_table.get(table_id)
        cell = resolved_cells.get(table_id)
        if candidate is None or cell is None or cell.status != "CONFIRMED":
            return None
        try:
            official = official_fetcher.fetch(cell, article_date=article_date)
        except Exception:
            return None
        publication = official.publication
        if (official.status != "SUCCESS" or official.value is None or publication is None
                or publication.status != "VERIFIED" or publication.published_at is None):
            return None
        signatures.add((official.value, cell.unit, publication.published_at))
        selected = selected or (candidate, cell)
    return selected if len(signatures) == 1 else None

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
def _value_provenance(
    evidence_cell: EvidenceCellSchema, official_value: KosisValue
) -> OfficialValueProvenanceSchema:
    publication = official_value.publication
    return OfficialValueProvenanceSchema(
        evidence_key=evidence_cell.canonical_key,
        source=official_value.source,
        content_hash=official_value.snapshot_hash,
        publication=(
            OfficialPublicationProvenanceSchema(
                status=publication.status,
                published_at=publication.published_at,
                pub_period=publication.pub_period,
                pub_date_text=publication.pub_date_text,
                publication_method_url=publication.publication_method_url,
                source_url=publication.source_url,
                retrieved_at=publication.retrieved_at,
                content_hash=publication.content_hash,
            )
            if publication is not None
            else None
        ),
    )

def _hold(
    claim: ClaimSchema,
    recorder: VerificationTraceRecorder,
    reason_code: str,
    explanation: str,
    *,
    evidence_cells: list[EvidenceCellSchema] | None = None,
    official_value_provenance: list[OfficialValueProvenanceSchema] | None = None,
) -> VerdictSchema:
    verdict = make_verdict(claim.claim_id, claim.value, [], None)
    return attach_trace(
        verdict.model_copy(update={
            "reason_code": reason_code, "explanation": explanation,
            "evidence_cells": evidence_cells or [],
            "official_value_provenance": official_value_provenance or [],
        }),
        recorder.build(),
    )


def _claim_tolerance(claim: ClaimSchema) -> float:
    """Accept only the explicit reporting precision present in the article text."""
    if claim.unit != "명":
        return 0.01
    source = claim.source_sentence
    if "천" in source or re.search(r"\d+\s*만\s*\d{1,4}(?!\s*[천백십])", source):
        # "2804만1000명" and "2천804만 명" both state a count only to
        # the nearest thousand people; a KOSIS 천명 value can retain hundreds.
        return 500.0
    return 0.01
