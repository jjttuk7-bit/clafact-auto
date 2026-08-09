"""Attach immutable pipeline traces to verification results."""
from schemas.pipeline_trace import PipelineTraceSchema
from schemas.verdict import VerdictSchema


def attach_trace(verdict: VerdictSchema, trace: PipelineTraceSchema) -> VerdictSchema:
    return verdict.model_copy(update={
        'execution_trace': trace,
        'preprocess_version': trace.preprocess_version,
        'claim_schema_version': trace.claim_schema_version,
        'semantic_standard_version': trace.semantic_standard_version,
        'kosis_catalog_version': trace.kosis_catalog_version,
        'matching_version': trace.matching_version,
        'calculation_version': trace.calculation_version,
    })
