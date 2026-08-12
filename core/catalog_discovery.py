"""Safe catalog discovery that keeps live search separate from coordinate resolution."""

from __future__ import annotations

from collections.abc import Iterable
import re

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
    return discovered


def build_catalog_discovery_queries(
    claim: ClaimSchema, concept: StandardConceptSchema
) -> list[str]:
    """Build KOSIS table-search queries from Concept plus searchable Claim context."""
    bases = _unique_texts((concept.canonical_name, claim.indicator, concept.matched_alias))
    if not bases:
        return []
    qualifiers = _unique_texts(
        value
        for value in (
            claim.region if claim.region not in {"전국", "대한민국", "한국"} else None,
            claim.population,
            *(claim.dimension or {}).values(),
        )
    )
    primary = bases[0]
    return [*bases, *(f"{primary} {qualifier}" for qualifier in qualifiers)]


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

def has_unresolved_live_metadata(candidates: Iterable[KosisCandidateSchema]) -> bool:
    """Identify candidates that prove a table search occurred but lack cell coordinates."""
    return any(item.metadata_status == "LIVE_SEARCH_UNRESOLVED" for item in candidates)
