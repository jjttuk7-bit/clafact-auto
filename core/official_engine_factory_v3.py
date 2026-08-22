"""Shared official engine with semantic, catalog, coordinate, and release overlays."""

from __future__ import annotations

from pathlib import Path

from core.catalog_binding import apply_catalog_binding
from core.evidence_resolver_v2 import install as install_coordinate_resolver
from core.kosis_publication_profiles_v2 import install_publication_profiles_v2
from core.official_engine_factory import (
    OfficialEnginePaths,
    _metadata_unavailable,
    build_official_evidence_service,
)
from core.official_evidence_service import CatalogResolution, OfficialEvidenceService
from core.semantic_normalizer_v3 import normalize_concept_v3
from core.semantic_standard_v2 import load_semantic_standard_v2

_OVERLAY_REQUIRED_TERMS = ("출생", "사망", "합계출산", "외식")


def build_official_evidence_service_v3(
    paths: OfficialEnginePaths,
    *,
    semantic_overlay_path: Path,
    catalog_overlay_path: Path,
    kosis_api_key: str | None,
    live_time_budget_seconds: float = 45.0,
    require_live_metadata: bool = False,
) -> OfficialEvidenceService:
    """Build the one official engine and isolate either catalog path's transient failure."""
    install_coordinate_resolver()
    install_publication_profiles_v2()
    base = build_official_evidence_service(
        paths, kosis_api_key=kosis_api_key,
        live_time_budget_seconds=live_time_budget_seconds,
        require_live_metadata=require_live_metadata,
    )
    overlay = build_official_evidence_service(
        OfficialEnginePaths(
            paths.standard_path, catalog_overlay_path,
            paths.as_of_metadata_paths, paths.metadata_manifest_paths,
        ),
        kosis_api_key=kosis_api_key,
        live_time_budget_seconds=live_time_budget_seconds,
        require_live_metadata=require_live_metadata,
    )
    concepts = load_semantic_standard_v2(paths.standard_path, semantic_overlay_path)

    def resolve_catalog(claim, concept):
        primary = _safe_resolution(base._catalog_resolver, claim, concept, "base_unavailable")
        needs_overlay = not primary.candidates or any(
            term in ((claim.indicator or "") + " " + claim.source_sentence)
            for term in _OVERLAY_REQUIRED_TERMS
        )
        fallback = (
            _safe_resolution(overlay._catalog_resolver, claim, concept, "overlay_unavailable")
            if needs_overlay else CatalogResolution(candidates=[], diagnostics={"overlay_skipped": 1})
        )
        if (
            not primary.candidates and not fallback.candidates
            and primary.diagnostics.get("base_unavailable")
            and fallback.diagnostics.get("overlay_unavailable")
        ):
            raise RuntimeError("KOSIS_CATALOG_UNAVAILABLE")
        return merge_catalog_resolutions(primary, fallback)

    return OfficialEvidenceService(
        concept_mapper=lambda claim: normalize_concept_v3(claim, concepts),
        catalog_resolver=resolve_catalog,
        official_fetcher=base._official_fetcher,
        candidate_selector=apply_catalog_binding,
    )


def merge_catalog_resolutions(base: CatalogResolution, overlay: CatalogResolution) -> CatalogResolution:
    merged = {(candidate.org_id, candidate.tbl_id): candidate for candidate in base.candidates}
    for candidate in overlay.candidates:
        merged[(candidate.org_id, candidate.tbl_id)] = candidate
    candidates = list(merged.values())
    flags = {
        key: value for source in (base.diagnostics, overlay.diagnostics)
        for key, value in source.items() if key.endswith(("_unavailable", "_skipped"))
    }
    counter_keys = {
        "attempted_queries", "failed_queries", "empty_queries",
        "metadata_itm_attempted", "metadata_itm_succeeded", "metadata_itm_failed",
        "metadata_prd_attempted", "metadata_prd_succeeded", "metadata_prd_failed",
    }
    counters = {
        key: sum(
            int(source.get(key, 0))
            for source in (base.diagnostics, overlay.diagnostics)
            if isinstance(source.get(key, 0), (int, float))
        )
        for key in counter_keys
    }
    metadata_unavailable = _metadata_unavailable(counters)
    return CatalogResolution(candidates=candidates, diagnostics={
        **base.diagnostics, **flags, **counters,
        "base_candidate_count": len(base.candidates),
        "overlay_candidate_count": len(overlay.candidates),
        "candidate_count": len(candidates),
        "metadata_unavailable": metadata_unavailable,
    })


def _safe_resolution(resolver, claim, concept, flag: str) -> CatalogResolution:
    try:
        value = resolver(claim, concept)
        return value if isinstance(value, CatalogResolution) else CatalogResolution(candidates=list(value), diagnostics={})
    except RuntimeError:
        return CatalogResolution(candidates=[], diagnostics={flag: 1})
