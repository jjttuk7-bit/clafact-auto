from core.catalog_metadata_refresh import refresh_item_metadata
from schemas.candidate import KosisCandidateSchema


def test_injected_snapshot_metadata_is_used_without_api_key() -> None:
    calls: list[tuple[str, str | None]] = []

    def snapshot_fetcher(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        calls.append((meta_type, api_key))
        if meta_type == "PRD":
            return [{
                "PRD_SE": "월",
                "STRT_PRD_DE": "2020.01",
                "END_PRD_DE": "2025.12",
            }]
        return [
            {
                "ORG_ID": org_id, "TBL_ID": table_id,
                "OBJ_ID": "ITEM", "OBJ_NM": "항목",
                "ITM_ID": "T", "ITM_NM": "수출액", "UNIT_NM": "천달러",
            },
            {
                "ORG_ID": org_id, "TBL_ID": table_id,
                "OBJ_ID": "C1", "OBJ_NM": "품목별",
                "ITM_ID": "00", "ITM_NM": "총계",
            },
        ]

    candidate = KosisCandidateSchema(
        org_id="134", tbl_id="DT_EXPORT", tbl_name="수출액",
        metadata_status="LIVE_SEARCH_UNRESOLVED",
    )
    refreshed = refresh_item_metadata(
        [candidate], None, metadata_fetcher=snapshot_fetcher,
        allow_without_api_key=True,
    )[0]

    assert [item[0] for item in calls] == ["ITM", "PRD"]
    assert refreshed.core_item_ids == ["T"]
    assert refreshed.dimension_member_codes == {"C1": {"총계": "00"}}
    assert refreshed.frequency == "월"
    assert refreshed.metadata_status == "OFFICIAL_METADATA_READY"

def test_cpi_detail_versioned_snapshot_hydrates_official_coordinates() -> None:
    from pathlib import Path
    from core.kosis_metadata_repository import KosisMetadataRepository

    root = Path(__file__).resolve().parents[2]
    repository = KosisMetadataRepository.from_manifests([
        root / "data/kosis_snapshots/cpi_detail_metadata_v1_manifest.json"
    ])
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1J22112", tbl_name="품목별 소비자물가지수",
        metadata_status="LIVE_SEARCH_UNRESOLVED",
    )

    refreshed = refresh_item_metadata(
        [candidate], None, metadata_fetcher=repository,
        allow_without_api_key=True, max_candidates=1,
    )[0]

    assert refreshed.metadata_status == "OFFICIAL_METADATA_READY"
    assert refreshed.core_item_ids == ["T"]
    assert refreshed.dimension_member_codes["C"]["전국"] == "T10"
    assert refreshed.dimension_member_codes["I"]["배추"] == "A02A01701"
    assert "월" in refreshed.frequency
