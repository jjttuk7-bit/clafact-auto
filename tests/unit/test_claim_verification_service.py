from core.pipeline_trace import PipelineTrace


def test_verification_trace_records_claim_and_catalog_stages() -> None:
    from core.claim_verification_service import VerificationTraceRecorder
    recorder = VerificationTraceRecorder('c1')
    trace = recorder.claim_parsed().concept_mapped().catalog_searched().build()
    assert [event.stage for event in trace.events] == ['CLAIM_PARSE', 'SEMANTIC_MAPPING', 'CATALOG_SEARCH']
from core.claim_verification_service import VerificationTraceRecorder


def test_trace_recorder_records_hold_at_evidence_stage() -> None:
    trace = VerificationTraceRecorder('c1').claim_parsed().evidence_held('MEMBER_CODE_UNRESOLVED').build()
    assert trace.events[-1].stage == 'EVIDENCE_CELL'
    assert trace.events[-1].status == 'HOLD'
    assert trace.events[-1].reason_code == 'MEMBER_CODE_UNRESOLVED'
from core.claim_verification_service import VerificationTraceRecorder


def test_trace_recorder_records_hard_guard_hold_and_match_margin() -> None:
    trace = (VerificationTraceRecorder('c1').claim_parsed()
        .hard_guard_held('UNIT_CONFLICT')
        .semantic_matched('AUTO', 'MATCH_ACCEPTED', 0.42)
        .build())
    assert trace.events[-2].stage == 'HARD_GUARD'
    assert trace.events[-2].status == 'HOLD'
    assert trace.events[-1].stage == 'SEMANTIC_MATCH'
    assert trace.events[-1].output_ref == 'margin=0.42'


def test_trace_recorder_records_complete_success_path() -> None:
    trace = (
        VerificationTraceRecorder("c1")
        .claim_parsed()
        .concept_mapped()
        .catalog_searched()
        .hard_guard_passed()
        .semantic_matched("AUTO", "MATCH_ACCEPTED", 1.0)
        .verification_succeeded()
        .build()
    )

    assert [event.stage for event in trace.events[-4:]] == [
        "EVIDENCE_CELL",
        "OFFICIAL_VALUE_FETCH",
        "CALCULATION",
        "VERDICT",
    ]
    assert all(event.status == "PASS" for event in trace.events[-4:])

def test_registered_growth_profile_records_guard_and_match_as_pass() -> None:
    trace = (
        VerificationTraceRecorder("cpi-1")
        .registered_growth_profile_matched()
        .build()
    )

    assert [event.stage for event in trace.events] == [
        "HARD_GUARD",
        "SEMANTIC_MATCH",
    ]
    assert all(event.status == "PASS" for event in trace.events)
    assert trace.events[0].output_ref == "registered_growth_profile"
    assert trace.events[1].output_ref == "exact_registered_profile"