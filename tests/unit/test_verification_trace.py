from core.pipeline_trace import PipelineTrace


def test_trace_recorder_attaches_stage_events_to_verdict() -> None:
    from core.verification_trace import attach_trace
    from core.verdict_engine import make_verdict

    trace = PipelineTrace.for_claim('c1', preprocess_version='1.0', claim_schema_version='1.0').pass_stage('CLAIM_PARSE').pass_stage('SEMANTIC_MAPPING')
    verdict = attach_trace(make_verdict('c1', 1.0, [1.0], 1.0), trace)
    assert [event.stage for event in verdict.execution_trace.events] == ['CLAIM_PARSE', 'SEMANTIC_MAPPING']
