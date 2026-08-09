"""Rule-based final verdicts from deterministic calculations."""

from schemas.pipeline_trace import PipelineTraceSchema
from schemas.verdict import VerdictSchema


def make_verdict(
    claim_id: str,
    claim_value: float | None,
    evidence_values: list[float],
    calculated_value: float | None,
    *,
    tolerance: float = 0.0,
    trace: PipelineTraceSchema | None = None,
) -> VerdictSchema:
    """Return an auditable verdict without generating official values."""
    if claim_value is None or calculated_value is None:
        verdict, route, reason, explanation = "UNDETERMINED", "HOLD", "VALUE_UNAVAILABLE", "Official value is unavailable."
    elif abs(claim_value - calculated_value) <= tolerance:
        verdict, route, reason, explanation = "MATCH", "AUTO", "WITHIN_TOLERANCE", "Claim matches the official calculation."
    else:
        verdict, route, reason, explanation = "MISMATCH", "AUTO", "OUTSIDE_TOLERANCE", "Claim differs from the official calculation."
    versions = trace or PipelineTraceSchema(
        claim_id=claim_id,
        preprocess_version="1.0",
        claim_schema_version="1.0",
    ).pass_stage("VERDICT")
    return VerdictSchema(
        claim_id=claim_id,
        claim_value=claim_value,
        evidence_values=evidence_values,
        calculated_value=calculated_value,
        verdict=verdict,
        route_status=route,
        reason_code=reason,
        explanation=explanation,
        dataset_version="unversioned",
        preprocess_version=versions.preprocess_version,
        claim_schema_version=versions.claim_schema_version,
        semantic_standard_version=versions.semantic_standard_version,
        kosis_catalog_version=versions.kosis_catalog_version,
        matching_version=versions.matching_version,
        calculation_version=versions.calculation_version,
        execution_trace=versions,
    )