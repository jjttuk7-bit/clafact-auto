"""Score only Hard Guard-compatible KOSIS candidates."""

from __future__ import annotations

from collections.abc import Iterable
from difflib import SequenceMatcher

from core.hard_guard import apply_hard_guard
from core.unit_normalizer import compatible_units
from schemas.candidate import KosisCandidateSchema, MatchResult
from schemas.claim import ClaimSchema


def semantic_match(
    claim: ClaimSchema,
    candidates: Iterable[KosisCandidateSchema],
    *,
    minimum_score: float = 0.7,
    min_margin: float = 0.1,
) -> list[MatchResult]:
    """Run Hard Guard first; use structural simplicity only to break ties."""
    scored = [
        (_score(claim, candidate), candidate)
        for candidate in candidates
        if apply_hard_guard(claim, candidate).passed
    ]
    ranked = [
        (score - 0.15 * _unrequested_axis_count(claim, candidate), score, candidate)
        for score, candidate in scored
    ]
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2].tbl_id, item[2].org_id))
    if not ranked:
        return []
    margin = ranked[0][0] - ranked[1][0] if len(ranked) > 1 else 1.0
    route_status, reason = _route(ranked[0][1], margin, minimum_score, min_margin)
    return [
        MatchResult(
            candidate_tbl_id=candidate.tbl_id,
            semantic_score=round(score, 6),
            top1_top2_margin=round(margin, 6) if index == 0 else None,
            route_status=route_status if index == 0 else "HOLD",
            reason_code=reason if index == 0 else "NON_TOP_CANDIDATE",
        )
        for index, (_rank_score, score, candidate) in enumerate(ranked)
    ]

def _score(claim: ClaimSchema, candidate: KosisCandidateSchema) -> float:
    indicators = _indicator_variants(claim)
    labels = [_normalize(label) for label in [candidate.tbl_name, *candidate.core_item_names]]
    label_score = max(
        (_label_similarity(indicator, label) for indicator in indicators for label in labels),
        default=0.0,
    )
    compatibility = 0.0
    if claim.unit and any(compatible_units(claim.unit, unit) for unit in candidate.unit_names):
        compatibility += 0.1
    if claim.frequency and claim.frequency in {
        part.strip() for part in (candidate.frequency or "").split("|")
    }:
        compatibility += 0.1
    compatibility += _aggregate_scope_score(claim, candidate)
    compatibility -= _series_transformation_penalty(claim, candidate)

    return 0.8 * label_score + compatibility


def _series_transformation_penalty(claim: ClaimSchema, candidate: KosisCandidateSchema) -> float:
    """Do not treat seasonal-adjusted and raw series as interchangeable."""
    candidate_name = _normalize(candidate.tbl_name)
    claim_text = _normalize(" ".join(
        value for value in [claim.source_sentence, claim.indicator, *(claim.dimension or {}).values()] if value
    ))
    is_seasonally_adjusted = "계절조정" in candidate_name
    asks_for_seasonal_adjustment = "계절조정" in claim_text or "계절조절" in claim_text
    if is_seasonally_adjusted and not asks_for_seasonal_adjustment:
        return 0.25
    return 0.0

def _unrequested_axis_count(claim: ClaimSchema, candidate: KosisCandidateSchema) -> int:
    """Prefer the least-disaggregated table after Claim slots are satisfied."""
    requested_axes = len(claim.dimension or {})
    if claim.region and claim.region not in {"전국", "대한민국", "한국"}:
        requested_axes += 1
    candidate_axes = len(candidate.dimension_ids or candidate.dimension_names)
    return max(0, candidate_axes - requested_axes)


def _indicator_variants(claim: ClaimSchema) -> set[str]:
    indicator = _normalize(claim.indicator or "")
    variants = {indicator} if indicator else set()
    if indicator.endswith("액"):
        variants.add(f"{indicator[:-1]}금액")
    for value in (claim.dimension or {}).values():
        member = _normalize(value)
        residual = indicator.replace(member, "") if member else indicator
        if len(residual) >= 2:
            variants.add(residual)
    return variants


def _aggregate_scope_score(claim: ClaimSchema, candidate: KosisCandidateSchema) -> float:
    """Prefer explicitly total tables for dimensionless national aggregate Claims."""
    if claim.dimension or claim.population:
        return 0.0
    if claim.region not in {None, "전국", "대한민국", "한국"}:
        return 0.0
    table_name = _normalize(candidate.tbl_name)
    return 0.15 if any(token in table_name for token in ("총괄", "총계", "전체")) else 0.0

def _label_similarity(indicator: str, label: str) -> float:
    if len(indicator) >= 2 and indicator in label:
        return 1.0
    return SequenceMatcher(None, indicator, label).ratio()


def _route(score: float, margin: float, minimum_score: float, min_margin: float) -> tuple[str, str]:
    if score < minimum_score:
        return "HOLD", "LOW_SEMANTIC_SCORE"
    if margin < min_margin:
        return "HOLD", "AMBIGUOUS_MARGIN"
    return "AUTO", "MATCH_ACCEPTED"


def _normalize(value: str) -> str:
    return "".join(value.split()).casefold()
