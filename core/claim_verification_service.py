"""Trace recorder for the shared verification service."""
from core.pipeline_trace import PipelineTrace
from schemas.pipeline_trace import PipelineTraceSchema

class VerificationTraceRecorder:
    def __init__(self, claim_id: str) -> None:
        self._trace = PipelineTrace.for_claim(claim_id, preprocess_version='1.0', claim_schema_version='1.0')
    def claim_parsed(self) -> 'VerificationTraceRecorder':
        self._trace = self._trace.pass_stage('CLAIM_PARSE'); return self
    def concept_mapped(self) -> 'VerificationTraceRecorder':
        self._trace = self._trace.pass_stage('SEMANTIC_MAPPING'); return self
    def catalog_searched(self) -> 'VerificationTraceRecorder':
        self._trace = self._trace.pass_stage('CATALOG_SEARCH'); return self
    def build(self) -> PipelineTraceSchema:
        return self._trace

    def evidence_held(self, reason_code: str) -> 'VerificationTraceRecorder':
        self._trace = self._trace.hold('EVIDENCE_CELL', reason_code); return self

    def evidence_confirmed(self) -> 'VerificationTraceRecorder':
        self._trace = self._trace.pass_stage('EVIDENCE_CELL'); return self

    def official_value_fetched(self) -> 'VerificationTraceRecorder':
        self._trace = self._trace.pass_stage('OFFICIAL_VALUE_FETCH'); return self

    def calculation_completed(self) -> 'VerificationTraceRecorder':
        self._trace = self._trace.pass_stage('CALCULATION'); return self

    def verdict_completed(self) -> 'VerificationTraceRecorder':
        self._trace = self._trace.pass_stage('VERDICT'); return self

    def hard_guard_passed(self) -> 'VerificationTraceRecorder':
        self._trace = self._trace.pass_stage('HARD_GUARD'); return self

    def hard_guard_held(self, reason_code: str) -> 'VerificationTraceRecorder':
        self._trace = self._trace.hold('HARD_GUARD', reason_code); return self

    def semantic_matched(self, route_status: str, reason_code: str, margin: float | None) -> 'VerificationTraceRecorder':
        output_ref = f'margin={margin}' if margin is not None else None
        if route_status == 'AUTO':
            self._trace = self._trace.pass_stage('SEMANTIC_MATCH', output_ref=output_ref)
        else:
            self._trace = self._trace.hold('SEMANTIC_MATCH', reason_code)
        return self
