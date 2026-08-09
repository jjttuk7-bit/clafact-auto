"""Rule-based final verdicts from deterministic calculations."""

from schemas.verdict import VerdictSchema


def make_verdict(claim_id: str, claim_value: float | None, evidence_values: list[float], calculated_value: float | None, *, tolerance: float = 0.0) -> VerdictSchema:
    """Return an auditable verdict without generating official values."""
    if claim_value is None or calculated_value is None:
        verdict, route, reason, explanation = "UNDETERMINED", "HOLD", "VALUE_UNAVAILABLE", "Official value is unavailable."
    elif abs(claim_value - calculated_value) <= tolerance:
        verdict, route, reason, explanation = "MATCH", "AUTO", "WITHIN_TOLERANCE", "Claim matches the official calculation."
    else:
        verdict, route, reason, explanation = "MISMATCH", "AUTO", "OUTSIDE_TOLERANCE", "Claim differs from the official calculation."
    return VerdictSchema(claim_id=claim_id, claim_value=claim_value, evidence_values=evidence_values, calculated_value=calculated_value, verdict=verdict, route_status=route, reason_code=reason, explanation=explanation, dataset_version="unversioned", semantic_standard_version="1.0", kosis_catalog_version="1.0", matching_version="1.0", calculation_version="1.0")
