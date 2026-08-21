"""Canonical runtime shared by Streamlit, batch, and Registry CLI adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from core import claim_extractor_factory
from core.admission_recovery import OfficialEvidenceResolver
from core.claim_parser import StructuredClaimExtractor
from core.official_engine_factory import OfficialEnginePaths
from core.official_engine_factory_v3 import build_official_evidence_service_v3
from core.operational_error import run_operational_stage
from core.unified_claim_pipeline import (
    ArticlePipelineResult,
    PipelineEntry,
    verify_article,
    verify_registry_record,
)
from schemas.claim_registry import ClaimRegistryRecord


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STANDARD_PATH = PROJECT_ROOT / "data" / "semantic_standard" / "concept_seed_v1.json"
CATALOG_PATH = PROJECT_ROOT / "data" / "kosis_catalog" / "catalog_350.json"
SEMANTIC_OVERLAY_PATH = PROJECT_ROOT / "data" / "semantic_standard" / "concept_overlay_v3.json"
CATALOG_OVERLAY_PATH = PROJECT_ROOT / "data" / "kosis_catalog" / "catalog_overlay_v2.json"
AS_OF_METADATA_PATHS = [
    PROJECT_ROOT / "data" / "kosis_snapshots" / "goldset_pilot.json",
    PROJECT_ROOT / "data" / "kosis_snapshots" / "official_goldset_asof_v3.json",
    PROJECT_ROOT / "data" / "kosis_snapshots" / "official_cpi_202510.json",
    PROJECT_ROOT / "data" / "kosis_snapshots" / "official_goldset_v3_news_b023.json",
    PROJECT_ROOT / "data" / "kosis_snapshots" / "official_cpi_detail_current_axes_v1.json",
]
METADATA_MANIFEST_PATHS = [
    PROJECT_ROOT / "data" / "kosis_snapshots" / "cpi_detail_metadata_v1_manifest.json",
    PROJECT_ROOT / "data" / "kosis_snapshots" / "gold_standard_v1_metadata_manifest.json",
]


@dataclass(frozen=True, slots=True)
class CanonicalPipeline:
    """Bind one Structured Output extractor to one v3 official engine."""

    extractor: StructuredClaimExtractor
    official_service: OfficialEvidenceResolver

    def verify_article(
        self,
        article_text: str,
        *,
        article_published_at: date | None,
        article_id: str | None = None,
    ) -> ArticlePipelineResult:
        return verify_article(
            article_text,
            article_published_at=article_published_at,
            extractor=self.extractor,
            official_service=self.official_service,
            article_id=article_id,
        )

    def verify_record(
        self,
        record: ClaimRegistryRecord,
        *,
        article_context: str | None = None,
        allow_structured_recovery: bool = True,
    ) -> list[PipelineEntry]:
        return verify_registry_record(
            record,
            extractor=self.extractor,
            official_service=self.official_service,
            article_context=article_context,
            allow_structured_recovery=allow_structured_recovery,
        )


def build_canonical_pipeline(
    settings: Any,
    *,
    live_time_budget_seconds: float = 45.0,
) -> CanonicalPipeline:
    """Construct the only production runtime, backed by official engine v3."""
    api_key = getattr(settings, "kosis_api_key", None)
    extractor = run_operational_stage(
        "CLAIM_PARSE",
        lambda: create_claim_extractor(settings),
    )
    paths = OfficialEnginePaths(
        STANDARD_PATH,
        CATALOG_PATH,
        [path for path in AS_OF_METADATA_PATHS if path.exists()],
        [path for path in METADATA_MANIFEST_PATHS if path.exists()],
    )
    service = build_official_evidence_service_v3(
        paths,
        semantic_overlay_path=SEMANTIC_OVERLAY_PATH,
        catalog_overlay_path=CATALOG_OVERLAY_PATH,
        kosis_api_key=api_key,
        live_time_budget_seconds=live_time_budget_seconds,
    )
    return CanonicalPipeline(
        extractor=extractor,
        official_service=service,
    )


def create_claim_extractor(settings: Any) -> StructuredClaimExtractor:
    return claim_extractor_factory.create_claim_extractor(settings)
