from core.pipeline_trace import PipelineTrace


def test_builds_three_branch_trace_summary() -> None:
    from core.trace_presentation import build_trace_summary
    trace = PipelineTrace.for_claim('c1', preprocess_version='1.0', claim_schema_version='1.0').pass_stage('CLAIM_PARSE').pass_stage('SEMANTIC_MAPPING').hold('EVIDENCE_CELL', 'MEMBER_CODE_UNRESOLVED')
    summary = build_trace_summary(trace)
    assert summary['무슨 통계'][-1]['stage'] == 'SEMANTIC_MAPPING'
    assert summary['어떤 데이터'][-1]['reason_code'] == 'MEMBER_CODE_UNRESOLVED'
    assert summary['어떻게 검증'] == []
