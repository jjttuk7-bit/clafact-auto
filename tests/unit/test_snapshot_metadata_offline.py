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
