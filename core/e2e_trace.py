"""Standard execution traces for reproducible E2E batch results."""

from schemas.pipeline_trace import PipelineTraceSchema


def build_e2e_trace(claim_id: str, *, route_status: str, reason_code: str | None, multi_evidence: bool = False) -> PipelineTraceSchema:
    """Create a stage-complete trace without exposing values or credentials."""
    trace = PipelineTraceSchema(claim_id=claim_id, route_status="AUTO", preprocess_version="registry-v1", claim_schema_version="claim-v1")
    trace = trace.pass_stage("CLAIM_PARSE").pass_stage("SEMANTIC_MAPPING", output_ref="PROFILE_FIRST").pass_stage("CATALOG_SEARCH", output_ref="PROFILE_FIRST_BYPASS")
    if route_status != "AUTO":
        return trace.hold("SEMANTIC_MATCH", reason_code or "E2E_HOLD")
    trace = trace.pass_stage("HARD_GUARD", output_ref="REGISTERED_PROFILE").pass_stage("SEMANTIC_MATCH", output_ref="EXACT_PROFILE").pass_stage("EVIDENCE_CELL").pass_stage("OFFICIAL_VALUE_FETCH")
    trace = trace.pass_stage("CALCULATION", output_ref="MULTI_EVIDENCE_CALCULATION" if multi_evidence else "DIRECT_VALUE_CALCULATION")
    return trace.pass_stage("VERDICT")
