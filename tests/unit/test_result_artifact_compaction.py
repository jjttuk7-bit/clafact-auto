from core.direct_value_multi_claim_results import compact_official_resolution


def test_compact_official_resolution_preserves_verdict_but_drops_large_member_maps() -> None:
    resolution = {
        "concept": {"concept_id": "C1", "status": "MATCHED"},
        "candidates": [
            {
                "org_id": "101",
                "tbl_id": "DT_1",
                "table_name": "고용",
                "dimension_member_codes": {"OBJ": {"전국": "00", "서울": "11"}},
            }
        ],
        "catalog_diagnostics": {"attempted_queries": 1},
        "verdict": {
            "route_status": "AUTO",
            "reason_code": "WITHIN_TOLERANCE",
            "official_value_provenance": [{"content_hash": "abc"}],
        },
    }

    compact = compact_official_resolution(resolution)

    assert compact["verdict"] == resolution["verdict"]
    assert compact["candidates"][0]["org_id"] == "101"
    assert "dimension_member_codes" not in compact["candidates"][0]
