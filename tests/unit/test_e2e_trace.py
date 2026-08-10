from core.e2e_trace import build_e2e_trace


def test_auto_trace_records_multi_evidence_calculation_stages() -> None:
    trace = build_e2e_trace("C1", route_status="AUTO", reason_code=None, multi_evidence=True)
    assert [event.stage for event in trace.events][-3:] == ["OFFICIAL_VALUE_FETCH", "CALCULATION", "VERDICT"]
    assert trace.events[-2].output_ref == "MULTI_EVIDENCE_CALCULATION"


def test_hold_trace_marks_the_failed_stage() -> None:
    trace = build_e2e_trace("C1", route_status="HOLD", reason_code="PROFILE_NOT_FOUND")
    assert trace.route_status == "HOLD"
    assert trace.events[-1].stage == "SEMANTIC_MATCH"
