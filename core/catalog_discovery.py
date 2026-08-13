"""Safe catalog discovery that keeps live search separate from coordinate resolution."""

from __future__ import annotations

from collections.abc import Iterable
import re

from core.claim_dimensions import dimension_member_values, normalized_dimension_members
from core.hard_guard import apply_hard_guard
from core.kosis_live_catalog import KosisLiveCatalogSearch
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def discover_catalog_candidates(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    local_candidates: Iterable[KosisCandidateSchema],
    live_search: KosisLiveCatalogSearch | None,
    *,
    max_live_queries: int | None = None,
) -> list[KosisCandidateSchema]:
    """Use local structural metadata first, then a read-only KOSIS table search."""
    local = list(local_candidates)
    if live_search is None or (local and _local_candidates_cover_claim_context(claim, local)):
        return local
    discovered = list(local)
    seen: set[tuple[str, str]] = {
        (candidate.org_id, candidate.tbl_id) for candidate in local
    }
    queries = build_catalog_discovery_queries(claim, concept)
    if max_live_queries is not None:
        queries = queries[:max(0, max_live_queries)]
    for query in queries:
        for candidate in live_search.search(query):
            key = (candidate.org_id, candidate.tbl_id)
            if key not in seen:
                seen.add(key)
                discovered.append(candidate)
    return rank_discovered_candidates(claim, concept, discovered)


def _local_candidates_cover_claim_context(
    claim: ClaimSchema, candidates: Iterable[KosisCandidateSchema]
) -> bool:
    """Return true when at least one local table represents every Claim dimension member."""
    requested_members = [
        _normalized_text(value)
        for value in dimension_member_values(claim.dimension)
        if _normalized_text(value)
    ]
    for candidate in candidates:
        if candidate.metadata_status == "LIVE_SEARCH_UNRESOLVED":
            continue
        if not apply_hard_guard(claim, candidate).passed:
            continue
        if not candidate.core_item_ids or not candidate.unit_names:
            continue
        if claim.frequency and not candidate.frequency:
            continue
        if not requested_members:
            return True
        represented = {
            _normalized_text(member)
            for members in candidate.dimension_members.values()
            for member in members
        }
        coded = {
            _normalized_text(member)
            for codes in candidate.dimension_member_codes.values()
            for member in codes
        }
        if all(
            member in represented and member in coded
            for member in requested_members
        ):
            return True
    return False


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
    bases = _unique_texts(
        value
        for value in (
            *concept.kosis_search_terms,
            concept.canonical_name,
            claim.indicator,
            concept.matched_alias,
        )
        if not _is_placeholder(value)
    )
    if not bases:
        return []
    dimension_values = _unique_texts(dimension_member_values(claim.dimension))
    region = claim.region if claim.region not in {"전국", "대한민국", "한국"} else None
    qualifiers = _unique_texts((*dimension_values, claim.population, region))
    contextual_bases = _unique_texts(
        value
        for value in (claim.indicator, concept.canonical_name, bases[0])
        if not _is_placeholder(value)
    )
    combined_context = _unique_texts((region, claim.population, *dimension_values))
    combined_queries = (
        _with_missing_context(base, combined_context)
        for base in contextual_bases
        if combined_context
    )
    contextual_queries = (
        _with_missing_context(base, (qualifier,))
        for qualifier in qualifiers
        for base in contextual_bases
    )
    return _unique_texts((*combined_queries, *contextual_queries, *bases))


def _is_placeholder(value: str | None) -> bool:
    return _normalized_text(value) in {"unresolved", "unknown", "na"}


def _with_missing_context(base: str, context: Iterable[str]) -> str:
    normalized_base = _normalized_text(base)
    missing = [
        value for value in context if _normalized_text(value) not in normalized_base
    ]
    return " ".join((*missing, base))


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
