from core.pipeline_run_reporting import build_run_report


def test_report_counts_terminal_routes_reasons_and_execution_stages() -> None:
    rows = [
        {
            "recovery_action": "DIRECT",
            "admission_route": "KOSIS_PIPELINE_ELIGIBLE",
            "terminal_status": "AUTO",
            "reason_code": "WITHIN_TOLERANCE",
            "diagnostic_id": None,
            "official_resolution": {
                "catalog_diagnostics": {
                    "attempted_queries": 2,
                    "failed_queries": 1,
                    "empty_queries": 0,
                    "metadata_itm_attempted": 1,
                    "metadata_itm_succeeded": 1,
                    "metadata_prd_attempted": 1,
                    "metadata_prd_failed": 1,
                },
                "verdict": {
                    "route_status": "AUTO",
                    "reason_code": "WITHIN_TOLERANCE",
                    "execution_trace": {
                        "events": [
                            {"stage": "CATALOG_SEARCH", "status": "PASS"},
                            {"stage": "OFFICIAL_VALUE_FETCH", "status": "PASS"},
                        ]
                    },
                    "official_value_provenance": [
                        {"source": "API", "publication": {"status": "VERIFIED"}}
                    ],
                }
            },
        },
        {
            "recovery_action": "NO_RECOVERY",
            "admission_route": "KOSIS_PIPELINE_ELIGIBLE",
            "terminal_status": "HOLD",
            "reason_code": "KOSIS_CATALOG_UNAVAILABLE",
            "diagnostic_id": "diag-1",
            "official_resolution": None,
        },
    ]

    report = build_run_report(rows, input_count=2, registry_errors=[])

    assert report["terminal_route_counts"] == {"AUTO": 1, "HOLD": 1}
    assert report["terminal_reason_counts"] == {
        "KOSIS_CATALOG_UNAVAILABLE": 1,
        "WITHIN_TOLERANCE": 1,
    }
    assert report["stage_status_counts"] == {
        "CATALOG_SEARCH": {"PASS": 1},
        "OFFICIAL_VALUE_FETCH": {"PASS": 1},
    }
    assert report["official_resolution_count"] == 1
    assert report["operational_failure_count"] == 1
    assert report["all_claims_terminal"] is True

    assert report["official_api_counts"] == {
        "catalog_query_attempted": 2,
        "catalog_query_failed": 1,
        "catalog_query_empty": 0,
        "catalog_query_succeeded_nonempty": 1,
        "metadata_itm_attempted": 1,
        "metadata_itm_succeeded": 1,
        "metadata_itm_failed": 0,
        "metadata_prd_attempted": 1,
        "metadata_prd_succeeded": 0,
        "metadata_prd_failed": 1,
        "official_value_fetch_pass": 1,
        "official_value_fetch_hold": 0,
        "api_provenance_claims": 1,
        "api_provenance_cells": 1,
        "verified_publication_claims": 1,
    }


def test_empty_run_is_not_terminally_complete() -> None:
    report = build_run_report([], input_count=1, registry_errors=[])

    assert report["all_claims_terminal"] is False
    assert report["input_coverage_complete"] is False


def test_coverage_counts_registry_identity_when_claim_ids_repeat() -> None:
    rows = [
        {
            "article_id": article_id,
            "sentence_id": "1",
            "parent_claim_id": "same-claim-id",
            "terminal_status": "HOLD",
            "reason_code": "TEST_HOLD",
            "official_resolution": None,
        }
        for article_id in ("article-1", "article-2")
    ]

    report = build_run_report(rows, input_count=2, registry_errors=[])

    assert report["input_coverage_complete"] is True
