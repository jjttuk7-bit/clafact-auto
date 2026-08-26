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
    RecordComparisonSummarySchema,
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
    tie_selected = _resolve_official_evidence_tie(
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
    record_fetch = getattr(official_fetcher, "fetch_record_history", None)
    try:
        if calculation_type in {"RECORD_HIGH", "RECORD_LOW"}:
            if not callable(record_fetch):
                raise ValueError("KOSIS_RECORD_HISTORY_FETCH_REQUIRED")
            fetched_values = record_fetch(
                evidence_cells, article_date=article_date
            )
        elif callable(batch_fetch):
            fetched_values = batch_fetch(
                evidence_cells, article_date=article_date
            )
        else:
            fetched_values = [
                official_fetcher.fetch(item, article_date=article_date)
                for item in evidence_cells
            ]
        if len(fetched_values) != len(evidence_cells):
            raise ValueError("KOSIS_VALUE_RESPONSE_COUNT_MISMATCH")
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
    try:
        calculated = calculate(plan, [*official_values, *plan.literal_values])
    except (ArithmeticError, ValueError):
        recorder.calculation_held("CALCULATION_FAILED")
        return _hold(
            claim, recorder, "CALCULATION_FAILED",
            "Official values cannot produce the required deterministic calculation.",
            evidence_cells=evidence_cells,
            official_value_provenance=provenance,
        )
    recorder.calculation_completed()
    record_summary: RecordComparisonSummarySchema | None = None
    if calculation_type in {"RECORD_HIGH", "RECORD_LOW"}:
        verdict, record_summary = _record_verdict(
            claim, calculation_type, evidence_cells, official_values, calculated, cell.unit
        )
    elif calculation_type == "DIFFERENCE":
        directed_difference = _direction_checked_difference(calculated, claim)
        claim_unit_value = (
            directed_difference if _is_percentage_point_unit(claim.unit)
            else convert_value(directed_difference, cell.unit or "", claim.unit or "")
        )
    elif calculation_type in {"GROWTH_RATE", "SHARE"}:
        claim_unit_value = calculated
    else:
        claim_unit_value = convert_value(calculated, cell.unit or "", claim.unit or "")
    if calculation_type not in {"RECORD_HIGH", "RECORD_LOW"}:
        verdict = make_verdict(
            claim.claim_id, claim.value, official_values, claim_unit_value, tolerance=_claim_tolerance(claim)
        )
    recorder.verdict_completed()
    return attach_trace(
        verdict.model_copy(
            update={
                "evidence_cells": evidence_cells,
                "official_value_provenance": provenance,
                "record_comparison": record_summary,
            }
        ),
        recorder.build(),
    )


def _record_verdict(
    claim: ClaimSchema,
    calculation_type: str,
    evidence_cells: list[EvidenceCellSchema],
    official_values: list[float],
    record_value: float,
    official_unit: str | None,
) -> tuple[VerdictSchema, RecordComparisonSummarySchema]:
    source_unit = official_unit or ""
    target_unit = claim.unit or ""
    converted_record = convert_value(record_value, source_unit, target_unit)
    converted_current = convert_value(official_values[-1], source_unit, target_unit)
    tolerance = _claim_tolerance(claim)
    source_matches_current = (
        claim.value is not None
        and abs(claim.value - converted_current) <= tolerance
    )
    official_tolerance = max(1e-12, abs(record_value) * 1e-12)
    current_is_record = abs(official_values[-1] - record_value) <= official_tolerance
    confirmed = source_matches_current and current_is_record
    base = make_verdict(
        claim.claim_id,
        claim.value,
        official_values,
        converted_record,
        tolerance=tolerance,
    )
    verdict = base.model_copy(update={
        "verdict": "MATCH" if confirmed else "MISMATCH",
        "route_status": "AUTO",
        "reason_code": "RECORD_CONFIRMED" if confirmed else "RECORD_NOT_CONFIRMED",
        "explanation": (
            "The current official value equals the official historical record."
            if confirmed
            else "The current official value does not equal the official historical record."
        ),
    })
    record_periods = [
        cell.prd_de
        for cell, value in zip(evidence_cells, official_values, strict=True)
        if abs(value - record_value) <= max(1e-12, abs(record_value) * 1e-12)
    ]
    summary = RecordComparisonSummarySchema(
        comparison_type=calculation_type,
        start_period=evidence_cells[0].prd_de,
        end_period=evidence_cells[-1].prd_de,
        observed_count=len(official_values),
        record_value=record_value,
        record_unit=official_unit,
        record_periods=record_periods,
    )
    return verdict, summary



def _resolve_official_evidence_tie(
    claim: ClaimSchema,
    matches: list[object],
    candidates: list[KosisCandidateSchema],
    resolved_cells: dict[str, EvidenceCellSchema],
    official_fetcher: OfficialValueFetcher,
    article_date: date,
) -> tuple[KosisCandidateSchema, EvidenceCellSchema] | None:
    """Resolve ties only when every required official operand is identical."""
    if claim.calculation not in {None, "DIRECT_VALUE", "DIFFERENCE"} or len(matches) < 2:
        return None
    top_score = getattr(matches[0], "semantic_score", None)
    tied_ids = [getattr(match, "candidate_tbl_id") for match in matches if getattr(match, "semantic_score", None) == top_score]
    if len(tied_ids) < 2:
        return None
    by_table = {candidate.tbl_id: candidate for candidate in candidates}
    signatures: set[tuple[tuple[float, str | None, date], ...]] = set()
    selected: tuple[KosisCandidateSchema, EvidenceCellSchema] | None = None
    for table_id in tied_ids:
        candidate = by_table.get(table_id)
        cell = resolved_cells.get(table_id)
        if candidate is None or cell is None or cell.status != "CONFIRMED":
            return None
        plan = build_calculation_plan(claim, cell, candidate)
        if plan is None:
            return None
        try:
            batch_fetch = getattr(official_fetcher, "fetch_many", None)
            officials = (
                batch_fetch(plan.required_cells, article_date=article_date)
                if callable(batch_fetch)
                else [
                    official_fetcher.fetch(item, article_date=article_date)
                    for item in plan.required_cells
                ]
            )
        except Exception:
            return None
        if len(officials) != len(plan.required_cells):
            return None
        signature: list[tuple[float, str | None, date]] = []
        for evidence_cell, official in zip(plan.required_cells, officials, strict=True):
            publication = official.publication
            if (
                official.status != "SUCCESS"
                or official.value is None
                or publication is None
                or publication.status != "VERIFIED"
                or publication.published_at is None
            ):
                return None
            signature.append((official.value, evidence_cell.unit, publication.published_at))
        signatures.add(tuple(signature))
        selected = selected or (candidate, cell)
    return selected if len(signatures) == 1 else None

def _prefer_exact_concept_code(
    concept: StandardConceptSchema,
    candidates: list[KosisCandidateSchema],
) -> list[KosisCandidateSchema]:
    """Narrow ties only when official metadata contains the Concept's exact code."""
    if concept.concept_id.startswith("OBSERVED:") or concept.standard_key.startswith(
        "observed_indicator_"
    ):
        return candidates
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
        source_url=official_value.source_url,
        retrieved_at=official_value.retrieved_at,
        value_last_changed_at=official_value.value_last_changed_at,
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
                evidence_scope=publication.evidence_scope,
                reference_period=publication.reference_period,
                coverage_start_period=publication.coverage_start_period,
                coverage_end_period=publication.coverage_end_period,
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


def _percent_reporting_tolerance(claim: ClaimSchema) -> float | None:
    """Return half the smallest percentage unit explicitly reported in the article."""
    if claim.value is None or "%" not in (claim.unit or ""):
        return None
    decimal_places: list[int] = []
    pattern = re.compile(
        r"(?P<number>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<decimals>\d+))?)\s*[％%]"
    )
    for match in pattern.finditer(claim.source_sentence):
        reported = float(match.group("number").replace(",", ""))
        if abs(abs(reported) - abs(claim.value)) <= max(1e-12, abs(claim.value) * 1e-9):
            decimal_places.append(len(match.group("decimals") or ""))
    if not decimal_places:
        return None
    return 0.5 * (10 ** -max(decimal_places))


def _claim_tolerance(claim: ClaimSchema) -> float:
    """Accept only the explicit reporting precision present in the article text."""
    if percent_tolerance := _percent_reporting_tolerance(claim):
        return percent_tolerance
    if claim.unit != "명":
        return 0.01
    source = claim.source_sentence
    if "천" in source or re.search(r"\d+\s*만\s*\d{1,4}(?!\s*[천백십])", source):
        # "2804만1000명" and "2천804만 명" both state a count only to
        # the nearest thousand people; a KOSIS 천명 value can retain hundreds.
        return 500.0
    return 0.01
