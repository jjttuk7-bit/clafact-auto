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
                "verdict": {
                    "route_status": "AUTO",
                    "reason_code": "WITHIN_TOLERANCE",
                    "execution_trace": {
                        "events": [
                            {"stage": "CATALOG_SEARCH", "status": "PASS"},
                            {"stage": "OFFICIAL_VALUE_FETCH", "status": "PASS"},
                        ]
                    },
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

