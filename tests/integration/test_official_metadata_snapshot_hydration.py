from pathlib import Path

from core.kosis_catalog_adapter import normalize_item_metadata
from core.kosis_metadata_repository import KosisMetadataRepository


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_versioned_official_snapshot_hydrates_large_item_and_member_coordinates() -> None:
    repository = KosisMetadataRepository.from_manifests([
        PROJECT_ROOT
        / "data"
        / "kosis_snapshots"
        / "gold_standard_v1_metadata_manifest.json"
    ])

    rows = repository("", "360", "DT_1R11001_FRM101", meta_type="ITM")
    structure = normalize_item_metadata(rows, table_id="DT_1R11001_FRM101")

    assert structure.item_codes["수출액"] == "13103112831T1"
    assert structure.dimension_ids["품목별"] == "13101112831A"
    assert len(structure.dimension_member_codes["13101112831A"]) > 4_000
    assert structure.dimension_member_codes["13101112831A"]["승용자동차 및 기타의 차량"] == "13102112831A.781"
