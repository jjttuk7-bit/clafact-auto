"""Build the production Core Engine for direct official KOSIS verification."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from core.catalog_discovery import discover_catalog_candidates
from core.catalog_metadata_refresh import refresh_item_metadata
from core.catalog_search import search_semantic_catalog
from core.data_loader import load_kosis_catalog, load_standard_concepts
from core.kosis_api_adapter import build_kosis_api_lookup
from core.kosis_fetcher import OfficialValueFetcher
from core.kosis_live_catalog import KosisLiveCatalogSearch
from core.kosis_metadata_repository import KosisMetadataRepository
from core.kosis_publication import KosisPublicationLookup
from core.official_evidence_service import OfficialEvidenceService
from core.semantic_normalizer import normalize_concept
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def build_live_official_evidence_service(
    *,
    kosis_api_key: str,
    standard_path: Path,
    catalog_path: Path,
    as_of_metadata_paths: Iterable[Path],
    metadata_repository: KosisMetadataRepository,
) -> OfficialEvidenceService:
    """Compose only direct KOSIS adapters into the shared official-evidence flow."""
    return OfficialEvidenceService(
        concept_mapper=lambda claim: normalize_concept(
            claim, load_standard_concepts(standard_path)
        ),
        catalog_resolver=lambda claim, concept: _resolve_catalog_candidates(
            claim,
            concept,
            kosis_api_key=kosis_api_key,
            catalog_path=catalog_path,
            metadata_repository=metadata_repository,
        ),
        official_fetcher=_build_official_fetcher(
            kosis_api_key, as_of_metadata_paths
        ),
    )


def _resolve_catalog_candidates(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    *,
    kosis_api_key: str,
    catalog_path: Path,
    metadata_repository: KosisMetadataRepository,
) -> list[KosisCandidateSchema]:
    local = search_semantic_catalog(claim, concept, load_kosis_catalog(catalog_path))
    live_search = (
        KosisLiveCatalogSearch(kosis_api_key, max_attempts=2, timeout_seconds=10)
        if kosis_api_key
        else None
    )
    discovered = discover_catalog_candidates(
        claim, concept, local, live_search, max_live_queries=3
    )
    if (
        live_search is not None
        and live_search.attempted_queries > 0
        and live_search.failed_queries == live_search.attempted_queries
    ):
        raise RuntimeError("KOSIS_CATALOG_UNAVAILABLE")
    refreshed = refresh_item_metadata(
        discovered,
        kosis_api_key,
        metadata_fetcher=metadata_repository,
        max_candidates=3,
        retries=2,
        timeout_seconds=10,
    )
    unavailable_statuses = {
        "OFFICIAL_ITEM_METADATA_UNAVAILABLE",
        "OFFICIAL_PERIOD_METADATA_UNAVAILABLE",
    }
    ready = [
        candidate for candidate in refreshed
        if candidate.metadata_status == "OFFICIAL_METADATA_READY"
    ]
    unavailable = [
        candidate for candidate in refreshed
        if candidate.metadata_status in unavailable_statuses
    ]
    concept_member_code = (
        concept.concept_id.rsplit(":", 1)[-1]
        if ":" in concept.concept_id
        else None
    )
    ready_for_concept = bool(ready)
    if concept_member_code:
        ready_for_concept = any(
            concept_member_code in codes.values()
            for candidate in ready
            for codes in candidate.dimension_member_codes.values()
        )
    if unavailable and not ready_for_concept:
        raise RuntimeError("KOSIS_METADATA_UNAVAILABLE")
    return refreshed


def _build_official_fetcher(
    kosis_api_key: str, as_of_metadata_paths: Iterable[Path]
) -> OfficialValueFetcher:
    api_lookup = build_kosis_api_lookup(kosis_api_key) if kosis_api_key else None
    return OfficialValueFetcher(
        [],
        api_lookup=api_lookup,
        prefer_api=api_lookup is not None,
        as_of_metadata_paths=as_of_metadata_paths,
        publication_lookup=KosisPublicationLookup(kosis_api_key),
        require_verified_release_metadata=True,
    )