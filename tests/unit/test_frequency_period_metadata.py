from core.catalog_metadata_refresh import _with_period_metadata, refresh_item_metadata
from schemas.candidate import KosisCandidateSchema


def test_refresh_preserves_each_official_period_range_by_frequency() -> None:
    def fetcher(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        if meta_type == "PRD":
            return [
                {"PRD_SE": "월", "STRT_PRD_DE": "1999.06", "END_PRD_DE": "2026.07"},
                {"PRD_SE": "분기", "STRT_PRD_DE": "1999 3/4", "END_PRD_DE": "2026 2/4"},
                {"PRD_SE": "년", "STRT_PRD_DE": "2000", "END_PRD_DE": "2025"},
            ]
        return [{
            "ORG_ID": org_id,
            "TBL_ID": table_id,
            "OBJ_ID": "ITEM",
            "OBJ_NM": "항목",
            "ITM_ID": "T90",
            "ITM_NM": "고용률",
            "UNIT_NM": "%",
        }]

    refreshed = refresh_item_metadata(
        [KosisCandidateSchema(
            org_id="101",
            tbl_id="DT_EMP",
            tbl_name="연령별 고용률",
            metadata_status="LIVE_SEARCH_UNRESOLVED",
        )],
        "secret",
        metadata_fetcher=fetcher,
    )[0]

    assert refreshed.period_ranges["월"].model_dump() == {
        "start_period": "1999.06", "end_period": "2026.07",
    }
    assert refreshed.period_ranges["분기"].model_dump() == {
        "start_period": "1999 3/4", "end_period": "2026 2/4",
    }
    assert refreshed.period_ranges["년"].model_dump() == {
        "start_period": "2000", "end_period": "2025",
    }


def test_refresh_reduces_duplicate_ranges_only_within_same_frequency() -> None:
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT", tbl_name="고용률",
        metadata_status="OFFICIAL_ITEM_METADATA_READY",
    )

    refreshed = _with_period_metadata(candidate, [
        {"PRD_SE": "월", "STRT_PRD_DE": "2001.01", "END_PRD_DE": "2025.12"},
        {"PRD_SE": "월", "STRT_PRD_DE": "1999.06", "END_PRD_DE": "2026.07"},
        {"PRD_SE": "분기", "STRT_PRD_DE": "1999 3/4", "END_PRD_DE": "2026 2/4"},
    ])

    assert refreshed.period_ranges["월"].start_period == "1999.06"
    assert refreshed.period_ranges["월"].end_period == "2026.07"
    assert refreshed.period_ranges["분기"].start_period == "1999 3/4"
