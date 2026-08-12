"""Safe catalog discovery that keeps live search separate from coordinate resolution."""

from __future__ import annotations

from collections.abc import Iterable
import re

from core.claim_dimensions import dimension_member_values, normalized_dimension_members
from core.kosis_live_catalog import KosisLiveCatalogSearch
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def discover_catalog_candidates(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    local_candidates: Iterable[KosisCandidateSchema],
    live_search: KosisLiveCatalogSearch | None,
) -> list[KosisCandidateSchema]:
    """Use local structural metadata first, then a read-only KOSIS table search."""
    local = list(local_candidates)
    if local or live_search is None:
        return local
    discovered: list[KosisCandidateSchema] = []
    seen: set[tuple[str, str]] = set()
    for query in build_catalog_discovery_queries(claim, concept):
        for candidate in live_search.search(query):
            key = (candidate.org_id, candidate.tbl_id)
            if key not in seen:
                seen.add(key)
                discovered.append(candidate)
    return rank_discovered_candidates(claim, concept, discovered)


def rank_discovered_candidates(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    candidates: Iterable[KosisCandidateSchema],
) -> list[KosisCandidateSchema]:
    """Rank table identities by official search vocabulary and Claim dimensions."""
    search_phrases = _unique_texts(
        (*concept.kosis_search_terms, concept.canonical_name, claim.indicator)
    )
    search_tokens = [
        token
        for phrase in search_phrases
        for token in re.split(r"\s+", phrase)
        if token
    ]
    normalized_dimensions = normalized_dimension_members(claim.dimension)
    dimension_tokens = [
        token
        for key, values in normalized_dimensions.items()
        for token in (key, *values)
        if token.strip()
    ]

    def score(candidate: KosisCandidateSchema) -> int:
        table_name = _normalized_text(candidate.tbl_name)
        search_score = sum(
            4 for token in search_tokens if _normalized_text(token) in table_name
        )
        dimension_score = sum(
            8 for token in dimension_tokens if _normalized_text(token) in table_name
        )
        return search_score + dimension_score

    return sorted(
        candidates,
        key=lambda candidate: (-score(candidate), candidate.tbl_id, candidate.org_id),
    )


def build_catalog_discovery_queries(
    claim: ClaimSchema, concept: StandardConceptSchema
) -> list[str]:
    """Build KOSIS table-search queries from Concept plus searchable Claim context."""
    bases = _unique_texts((*concept.kosis_search_terms, concept.canonical_name, claim.indicator, concept.matched_alias))
    if not bases:
        return []
    qualifiers = _unique_texts(
        value
        for value in (
            claim.region if claim.region not in {"전국", "대한민국", "한국"} else None,
            claim.population,
            *dimension_member_values(claim.dimension),
        )
    )
    contextual_bases = _unique_texts((claim.indicator, concept.canonical_name, bases[0]))
    contextual_queries = (
        f"{qualifier} {base}"
        for qualifier in qualifiers
        for base in contextual_bases
    )
    return _unique_texts((*contextual_queries, *bases))


def _unique_texts(values: Iterable[str | None]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip() if value else ""
        key = re.sub(r"[\s_-]+", "", text).casefold()
        if text and key not in seen:
            seen.add(key)
            unique.append(text)
    return unique


def _normalized_text(value: str | None) -> str:
    return re.sub(r"[\s_-]+", "", value or "").casefold()

def has_unresolved_live_metadata(candidates: Iterable[KosisCandidateSchema]) -> bool:
    """Identify candidates that prove a table search occurred but lack cell coordinates."""
    return any(item.metadata_status == "LIVE_SEARCH_UNRESOLVED" for item in candidates)
