"""Build the shared live KOSIS official-evidence engine outside the UI."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import re

from core.catalog_binding import apply_catalog_binding, seed_catalog_bindings
from core.structural_candidate_selector import select_official_candidate
from core.catalog_discovery import discover_catalog_candidates
from core.catalog_metadata_refresh import refresh_item_metadata_for_claim
from core.catalog_search import search_semantic_catalog
from core.data_loader import load_kosis_catalog, load_standard_concepts
from core.kosis_api_adapter import build_kosis_api_lookup
from core.kosis_fetcher import OfficialValueFetcher
from core.kosis_live_catalog import KosisLiveCatalogSearch
from core.kosis_metadata_repository import KosisMetadataRepository
from core.kosis_publication import KosisPublicationLookup
from core.official_evidence_service import CatalogResolution, OfficialEvidenceService
from core.semantic_normalizer import normalize_concept
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


@dataclass(frozen=True, slots=True)
class OfficialEnginePaths:
    standard_path: Path
    catalog_path: Path
    as_of_metadata_paths: list[Path]
    metadata_manifest_paths: list[Path] = field(default_factory=list)


def build_official_evidence_service(
    paths: OfficialEnginePaths, *, kosis_api_key: str | None,
    live_time_budget_seconds: float = 45.0,
    require_live_metadata: bool = False,
    live_catalog_cache: dict[str, tuple[KosisCandidateSchema, ...]] | None = None,
    metadata_repository: KosisMetadataRepository | None = None,
) -> OfficialEvidenceService:
    """Create the one live engine used by UI, batch, and API acceptance."""
    repository = metadata_repository or (
        KosisMetadataRepository.from_manifests(
            paths.metadata_manifest_paths, prefer_live=require_live_metadata
        )
        if paths.metadata_manifest_paths
        else KosisMetadataRepository([], prefer_live=require_live_metadata)
    )
    fetcher = OfficialValueFetcher(
        [],
        api_lookup=(build_kosis_api_lookup(
            kosis_api_key, retries=1,
            timeout_seconds=max(1.0, live_time_budget_seconds / 2),
        ) if kosis_api_key else None),
        prefer_api=bool(kosis_api_key),
        as_of_metadata_paths=paths.as_of_metadata_paths,
        publication_lookup=KosisPublicationLookup(kosis_api_key),
        require_verified_release_metadata=True,
    )

    def resolve_catalog(claim: ClaimSchema, concept: StandardConceptSchema):
        local = search_semantic_catalog(claim, concept, load_kosis_catalog(paths.catalog_path))
        live_options: dict[str, object] = {
            "max_attempts": 1,
            "timeout_seconds": max(1.0, min(10.0, live_time_budget_seconds / 4)),
        }
        if live_catalog_cache is not None:
            live_options["result_cache"] = live_catalog_cache
        live = KosisLiveCatalogSearch(kosis_api_key, **live_options) if kosis_api_key else None
        discovered = discover_catalog_candidates(
            claim, concept, local, live,
            time_budget_seconds=live_time_budget_seconds,
        )
        discovered = _add_official_concept_candidates(discovered, concept, repository)
        if live and not local and live.attempted_queries and live.failed_queries == live.attempted_queries:
            raise RuntimeError("KOSIS_CATALOG_UNAVAILABLE")

        # Catalog search has completed. A verified recurring binding now limits
        # which table receives the official ITM/PRD request. The binding runs
        # again after hydration in OfficialEvidenceService before Hard Guard.
        discovered = seed_catalog_bindings(claim, concept, discovered)
        discovered = apply_catalog_binding(claim, concept, discovered)
        metadata_diagnostics: Counter[str] = Counter()

        def observed_metadata_fetcher(
            api_key: str, org_id: str, table_id: str, *,
            meta_type: str = "ITM", **kwargs: object,
        ):
            phase = meta_type.strip().lower() or "unknown"
            metadata_diagnostics[f"metadata_{phase}_attempted"] += 1
            try:
                rows = repository(api_key, org_id, table_id, meta_type=meta_type, **kwargs)
            except (RuntimeError, TypeError, ValueError) as error:
                metadata_diagnostics[f"metadata_{phase}_failed"] += 1
                metadata_diagnostics[f"metadata_failure_{_safe_metadata_failure_code(error)}"] += 1
                raise
            metadata_diagnostics[f"metadata_{phase}_succeeded"] += 1
            return rows

        refreshed = refresh_item_metadata_for_claim(
            discovered, claim, kosis_api_key,
            metadata_fetcher=observed_metadata_fetcher,
            max_candidates=None,
            time_budget_seconds=live_time_budget_seconds,
            retries=2,
            timeout_seconds=min(10, live_time_budget_seconds),
        )
        metadata_diagnostics["metadata_unavailable"] = _metadata_unavailable(metadata_diagnostics)
        return CatalogResolution(candidates=refreshed, diagnostics={
            "local_candidate_count": len(local),
            "attempted_queries": live.attempted_queries if live else 0,
            "failed_queries": live.failed_queries if live else 0,
            "empty_queries": live.empty_queries if live else 0,
            "catalog_cache_hits": getattr(live, "cache_hits", 0) if live else 0,
            "candidate_count": len(refreshed),
            **dict(metadata_diagnostics),
        })

    return OfficialEvidenceService(
        concept_mapper=lambda claim: normalize_concept(
            claim, load_standard_concepts(paths.standard_path)
        ),
        catalog_resolver=resolve_catalog,
        official_fetcher=fetcher,
        candidate_selector=select_official_candidate,
    )


def _safe_metadata_failure_code(error: Exception) -> str:
    code = str(error).strip()
    if re.fullmatch(r"KOSIS_METADATA_(?:FETCH_FAILED|INVALID_RESPONSE|EMPTY_RESPONSE|API_ERROR(?:_\d+)?|SNAPSHOT_(?:HASH_MISMATCH|MANIFEST_INVALID|VERSION_MISMATCH|VERSION_REQUIRED))", code):
        return code
    if isinstance(error, TypeError):
        return "KOSIS_METADATA_CLIENT_TYPE_ERROR"
    if isinstance(error, ValueError):
        return "KOSIS_METADATA_CLIENT_VALUE_ERROR"
    return "KOSIS_METADATA_UNCLASSIFIED_FAILURE"


def _add_official_concept_candidates(
    candidates: list[KosisCandidateSchema], concept: StandardConceptSchema,
    repository: KosisMetadataRepository,
) -> list[KosisCandidateSchema]:
    if ":" not in concept.concept_id:
        return candidates
    code = concept.concept_id.rsplit(":", 1)[-1].strip()
    official_identities = set(repository.table_identities_for_member_code(code))
    prioritized = [
        candidate.model_copy(update={"source_stat_id": "OFFICIAL_CONCEPT_METADATA_SEED"})
        if (candidate.org_id, candidate.tbl_id) in official_identities else candidate
        for candidate in candidates
    ]
    existing = {(candidate.org_id, candidate.tbl_id) for candidate in prioritized}
    seeded = [
        KosisCandidateSchema(
            org_id=org_id, tbl_id=table_id, tbl_name=concept.canonical_name,
            source_stat_id="OFFICIAL_CONCEPT_METADATA_SEED",
            metadata_status="LIVE_SEARCH_UNRESOLVED",
        )
        for org_id, table_id in official_identities
        if (org_id, table_id) not in existing
    ]
    return [*seeded, *prioritized]


def _metadata_unavailable(diagnostics: Counter[str] | dict[str, int]) -> int:
    for phase in ("itm", "prd"):
        attempted = diagnostics.get(f"metadata_{phase}_attempted", 0)
        if (
            attempted
            and not diagnostics.get(f"metadata_{phase}_succeeded", 0)
            and diagnostics.get(f"metadata_{phase}_failed", 0) >= attempted
        ):
            return 1
    return 0
