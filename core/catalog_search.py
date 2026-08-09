"""Deterministic retrieval of KOSIS catalog candidates."""

from __future__ import annotations

import re
from collections.abc import Iterable

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
        _normalize(term)
        for term in (claim.indicator, concept.canonical_name, concept.matched_alias)
        if term
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
            scored.append((score, candidate))
    return [candidate for _, candidate in sorted(scored, key=lambda item: (-item[0], item[1].tbl_id, item[1].org_id))[:top_k]]


def _normalize(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value).casefold()
