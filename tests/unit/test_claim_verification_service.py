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
