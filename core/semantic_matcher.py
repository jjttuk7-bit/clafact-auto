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
    """Run Hard Guard first, score survivors, and hold ambiguous selections."""
    scored = [(_score(claim, candidate), candidate) for candidate in candidates if apply_hard_guard(claim, candidate).passed]
    scored.sort(key=lambda item: (-item[0], item[1].tbl_id, item[1].org_id))
    if not scored:
        return []
    margin = scored[0][0] - scored[1][0] if len(scored) > 1 else 1.0
    route_status, reason = _route(scored[0][0], margin, minimum_score, min_margin)
    return [
        MatchResult(
            candidate_tbl_id=candidate.tbl_id,
            semantic_score=round(score, 6),
            top1_top2_margin=round(margin, 6) if index == 0 else None,
            route_status=route_status if index == 0 else "HOLD",
            reason_code=reason if index == 0 else "NON_TOP_CANDIDATE",
        )
        for index, (score, candidate) in enumerate(scored)
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
    return 0.8 * label_score + compatibility


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
