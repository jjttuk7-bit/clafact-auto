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
    indicator = _normalize(claim.indicator or "")
    labels = [_normalize(label) for label in [candidate.tbl_name, *candidate.core_item_names]]
    label_score = max((SequenceMatcher(None, indicator, label).ratio() for label in labels), default=0.0)
    compatibility = 0.0
    if claim.unit and any(compatible_units(claim.unit, unit) for unit in candidate.unit_names):
        compatibility += 0.1
    if claim.frequency and claim.frequency == candidate.frequency:
        compatibility += 0.1
    return 0.8 * label_score + compatibility


def _route(score: float, margin: float, minimum_score: float, min_margin: float) -> tuple[str, str]:
    if score < minimum_score:
        return "HOLD", "LOW_SEMANTIC_SCORE"
    if margin < min_margin:
        return "HOLD", "AMBIGUOUS_MARGIN"
    return "AUTO", "MATCH_ACCEPTED"


def _normalize(value: str) -> str:
    return "".join(value.split()).casefold()
