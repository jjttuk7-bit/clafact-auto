"""Deterministic retrieval of KOSIS catalog candidates."""

from __future__ import annotations

import re
from collections.abc import Iterable

from core.unit_normalizer import compatible_units
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def search_semantic_catalog(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    candidates: Iterable[KosisCandidateSchema],
    *,
    top_k: int = 20,
) -> list[KosisCandidateSchema]:
    """Return lexical catalog candidates for a resolved semantic concept."""
    if top_k <= 0 or concept.status != "MATCHED":
        return []

    query_terms = {
        expanded
        for term in (claim.indicator, concept.canonical_name, concept.matched_alias)
        if term
        for expanded in _expand_query_term(term)
    }
    scored: list[tuple[int, KosisCandidateSchema]] = []
    for candidate in candidates:
        fields = [candidate.tbl_name, *candidate.core_item_names]
        normalized_fields = [_normalize(field) for field in fields]
        score = sum(
            2 if term in normalized_fields else 1
            for term in query_terms
            if any(term in field for field in normalized_fields)
        )
        if score:
            scored.append((score + _slot_compatibility_score(claim, candidate), candidate))
    return [candidate for _, candidate in sorted(scored, key=lambda item: (-item[0], item[1].tbl_id, item[1].org_id))[:top_k]]


def _normalize(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value).casefold()


def _expand_query_term(value: str) -> set[str]:
    """Keep the original term and Korean measurement-name stems for catalog recall."""
    normalized = _normalize(value)
    terms = {normalized}
    if len(normalized) > 1 and normalized[-1] in {"수", "액", "률"}:
        terms.add(normalized[:-1])
    return {term for term in terms if term}


def _slot_compatibility_score(claim: ClaimSchema, candidate: KosisCandidateSchema) -> int:
    """Rank lexical matches by non-negotiable structured Claim context."""
    score = 0
    if claim.frequency and candidate.frequency:
        frequencies = {_frequency_key(item) for item in candidate.frequency.split("|")}
        score += 6 if _frequency_key(claim.frequency) in frequencies else -3
    if (
        claim.unit
        and candidate.unit_names
        and claim.calculation not in {"GROWTH_RATE", "SHARE", "RATIO", "MULTIPLE"}
    ):
        score += 4 if any(compatible_units(claim.unit, unit) for unit in candidate.unit_names) else -2
    if claim.region and claim.region not in {"전국", "대한민국", "한국"}:
        score += 4 if _has_dimension(candidate, ("시도", "지역", "행정", "읍면")) else -2
    if claim.population and "세" in claim.population:
        score += 3 if _has_dimension(candidate, ("연령",)) else -2
    if claim.dimension:
        requested = tuple(claim.dimension.keys())
        score += sum(2 for key in requested if _has_dimension(candidate, (key,)))
    return score


def _has_dimension(candidate: KosisCandidateSchema, tokens: tuple[str, ...]) -> bool:
    return any(token in name for token in tokens for name in candidate.dimension_names)


def _frequency_key(value: str) -> str:
    normalized = _normalize(value)
    return {
        "monthly": "월", "month": "월", "m": "월",
        "yearly": "년", "year": "년", "annual": "년", "y": "년",
        "quarterly": "분기", "quarter": "분기", "q": "분기",
    }.get(normalized, normalized)