"""Safe catalog discovery that keeps live search separate from coordinate resolution."""

from __future__ import annotations

from collections.abc import Iterable

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
    query = claim.indicator or concept.canonical_name or concept.matched_alias
    return live_search.search(query) if query else []


def has_unresolved_live_metadata(candidates: Iterable[KosisCandidateSchema]) -> bool:
    """Identify candidates that prove a table search occurred but lack cell coordinates."""
    return any(item.metadata_status == "LIVE_SEARCH_UNRESOLVED" for item in candidates)
