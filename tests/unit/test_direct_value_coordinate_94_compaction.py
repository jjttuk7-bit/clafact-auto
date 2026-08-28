from core.direct_value_coordinate_94_compaction import compact_coordinate_result


def test_compaction_drops_large_dimension_maps_but_keeps_evidence() -> None:
    row = {
        "claim_id": "C1",
        "official_resolution": {
            "candidates": [{
                "org_id": "101", "tbl_id": "DT", "tbl_name": "표",
                "dimension_member_codes": {"A": {str(i): str(i) for i in range(100)}},
                "unit_names": ["천명"], "frequency": "월", "metadata_status": "OFFICIAL_METADATA_READY",
            }],
            "catalog_diagnostics": {"attempted_queries": 2},
            "verdict": {"evidence_cells": [{"canonical_key": "K1"}], "official_value_provenance": [{"content_hash": "abc"}]},
        },
    }

    compact = compact_coordinate_result(row)

    assert compact["official_resolution"]["candidate_count"] == 1
    assert "dimension_member_codes" not in compact["official_resolution"]["candidate_refs"][0]
    assert compact["official_resolution"]["verdict"]["evidence_cells"][0]["canonical_key"] == "K1"
