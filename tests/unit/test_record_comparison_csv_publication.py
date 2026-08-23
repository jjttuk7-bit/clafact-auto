from tools.run_record_comparison_group import _csv_row


def test_csv_records_actual_range_publication_and_row_change_dates() -> None:
    row = _csv_row({
        "run_id": "range",
        "claim": {"calculation": "RECORD_HIGH"},
        "official_resolution": {
            "verdict": {
                "route_status": "AUTO",
                "evidence_cells": [
                    {"org_id": "101", "tbl_id": "DT", "prd_de": "1999-06"},
                    {"org_id": "101", "tbl_id": "DT", "prd_de": "2025-06"},
                ],
                "official_value_provenance": [
                    {
                        "source": "API",
                        "content_hash": "same-range-hash",
                        "value_last_changed_at": "2009-03-18",
                        "publication": {
                            "status": "VERIFIED",
                            "evidence_scope": "CALCULATION_RANGE",
                            "reference_period": "2025-06",
                            "coverage_start_period": "1999-06",
                            "coverage_end_period": "2025-06",
                        },
                    },
                    {
                        "source": "API",
                        "content_hash": "same-range-hash",
                        "value_last_changed_at": "2025-07-03",
                        "publication": {
                            "status": "VERIFIED",
                            "evidence_scope": "CALCULATION_RANGE",
                            "reference_period": "2025-06",
                            "coverage_start_period": "1999-06",
                            "coverage_end_period": "2025-06",
                        },
                    },
                ],
            },
        },
    })

    assert row["publication_evidence_scope"] == "CALCULATION_RANGE"
    assert row["publication_reference_period"] == "2025-06"
    assert row["publication_coverage"] == "1999-06~2025-06"
    assert row["value_last_changed_dates"] == "2009-03-18|2025-07-03"
