"""Shared live official engine with the versioned repeated-domain semantic overlay."""

from __future__ import annotations

from pathlib import Path

from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from core.official_evidence_service import OfficialEvidenceService
from core.semantic_normalizer import normalize_concept
from core.semantic_standard_v2 import load_semantic_standard_v2


def build_official_evidence_service_v2(
    paths: OfficialEnginePaths,
    *,
    overlay_path: Path,
    kosis_api_key: str | None,
    live_time_budget_seconds: float = 45.0,
) -> OfficialEvidenceService:
    """Reuse the one official engine while replacing only its Concept repository."""
    base = build_official_evidence_service(
        paths,
        kosis_api_key=kosis_api_key,
        live_time_budget_seconds=live_time_budget_seconds,
    )
    concepts = load_semantic_standard_v2(paths.standard_path, overlay_path)
    return OfficialEvidenceService(
        concept_mapper=lambda claim: normalize_concept(claim, concepts),
        catalog_resolver=base._catalog_resolver,
        official_fetcher=base._official_fetcher,
    )
