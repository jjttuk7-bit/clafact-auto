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
