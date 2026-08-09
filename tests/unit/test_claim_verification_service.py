from core.pipeline_trace import PipelineTrace


def test_verification_trace_records_claim_and_catalog_stages() -> None:
    from core.claim_verification_service import VerificationTraceRecorder
    recorder = VerificationTraceRecorder('c1')
    trace = recorder.claim_parsed().concept_mapped().catalog_searched().build()
    assert [event.stage for event in trace.events] == ['CLAIM_PARSE', 'SEMANTIC_MAPPING', 'CATALOG_SEARCH']
