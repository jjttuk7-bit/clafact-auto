from pathlib import Path

from core.official_evidence_factory import build_live_official_evidence_service
from core.official_evidence_service import OfficialEvidenceService
from core.kosis_metadata_repository import KosisMetadataRepository


def test_live_factory_builds_one_service_with_direct_kosis_adapters() -> None:
    service = build_live_official_evidence_service(
        kosis_api_key="test-key",
        standard_path=Path("data/semantic_standard/concept_seed_v1.json"),
        catalog_path=Path("data/kosis_catalog/catalog_350.json"),
        as_of_metadata_paths=[],
        metadata_repository=KosisMetadataRepository([]),
    )

    assert isinstance(service, OfficialEvidenceService)