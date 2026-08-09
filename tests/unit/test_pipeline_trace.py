from core.article_preprocessor import preprocess_article
from core.pipeline_trace import PipelineTrace


def test_preprocess_article_records_all_selection_stages() -> None:
    result = preprocess_article(
        '기자 입력 2025.11.04. 08:00 소비자물가는 2.4% 상승했다. 관련 기사 광고 500억원 할인',
        preprocess_version='1.1',
    )

    assert result.clean_text == '소비자물가는 2.4% 상승했다.'
    assert result.sentences == ['소비자물가는 2.4% 상승했다.']
    assert result.claim_candidates == ['소비자물가는 2.4% 상승했다.']
    assert [(event.stage, event.status) for event in result.trace.events] == [
        ('PREPROCESS', 'PASS'),
        ('SENTENCE_SPLIT', 'PASS'),
        ('CLAIM_CANDIDATE_SELECTION', 'PASS'),
    ]
    assert result.trace.preprocess_version == '1.1'


def test_pipeline_trace_routes_hold_with_auditable_reason() -> None:
    trace = PipelineTrace.for_claim('claim-1', preprocess_version='1.1', claim_schema_version='1.0')
    trace = trace.pass_stage('CLAIM_PARSE', output_ref='claim-1')
    trace = trace.hold('EVIDENCE_CELL', 'EVIDENCE_CELL_UNRESOLVED')

    assert trace.route_status == 'HOLD'
    assert trace.events[-1].reason_code == 'EVIDENCE_CELL_UNRESOLVED'
    assert trace.events[-1].status == 'HOLD'
    assert trace.preprocess_version == '1.1'
    assert trace.claim_schema_version == '1.0'