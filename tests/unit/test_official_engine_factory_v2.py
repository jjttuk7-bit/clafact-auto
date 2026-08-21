from pathlib import Path

from core.official_engine_factory import OfficialEnginePaths
from core.official_engine_factory_v2 import build_official_evidence_service_v2
from schemas.claim import ClaimSchema


def test_v2_factory_uses_semantic_overlay_in_the_shared_service() -> None:
    service = build_official_evidence_service_v2(
        OfficialEnginePaths(
            standard_path=Path("data/semantic_standard/concept_seed_v1.json"),
            catalog_path=Path("data/kosis_catalog/catalog_350.json"),
            as_of_metadata_paths=[],
        ),
        overlay_path=Path("data/semantic_standard/concept_overlay_v2.json"),
        kosis_api_key=None,
    )
    concept = service._concept_mapper(ClaimSchema(
        claim_id="c",
        source_sentence="20대 쉬었음 인구는 37만8000명이었다.",
        indicator="쉬었음 인구",
        value=378000,
        unit="명",
        time="2025년",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    ))

    assert concept.standard_key == "inactive_population_resting"
