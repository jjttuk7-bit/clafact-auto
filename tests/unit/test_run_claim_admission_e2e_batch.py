from tools.run_claim_admission_e2e_batch import build_report


def test_report_separates_admission_outcomes_from_official_holds() -> None:
    report = build_report([
        {
            "admission_label": "KOSIS_PIPELINE_ELIGIBLE",
            "route_status": "AUTO",
            "verdict": "MATCH",
            "reason_code": "WITHIN_TOLERANCE",
        },
        {
            "admission_label": "CONTEXT_REQUIRED",
            "route_status": "ADMISSION_ROUTED",
            "verdict": "UNDETERMINED",
            "reason_code": "MISSING_TIME_CONTEXT",
        },
        {
            "admission_label": "KOSIS_PIPELINE_ELIGIBLE",
            "route_status": "HOLD",
            "verdict": "UNDETERMINED",
            "reason_code": "CONCEPT_NOT_FOUND",
        },
    ])

    assert report["admission_counts"] == {
        "CONTEXT_REQUIRED": 1,
        "KOSIS_PIPELINE_ELIGIBLE": 2,
    }
    assert report["official_route_counts"] == {"AUTO": 1, "HOLD": 1}
    assert report["admission_routed_count"] == 1
    assert report["official_hold_reason_counts"] == {"CONCEPT_NOT_FOUND": 1}
