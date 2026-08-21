"""Conservative repair of validated Structured Outputs before official replay."""

from datetime import date
from core.claim_contract import assess_claim_contract
from core.claim_time_resolver import resolve_relative_time
from core.deterministic_slot_enricher import infer_explicit_slots


def recover_validated_claim(claim, article_date: date | None):
    """Preserve accepted slots; repair only explicit period-comparison omissions."""
    if claim.parse_status == "AUTO_OK":
        return resolve_relative_time(claim, article_date)
    if claim.calculation != "DIFFERENCE" or not claim.time:
        return claim
    comparison = dict(claim.comparison or {})
    explicit = infer_explicit_slots(claim.source_sentence)
    for key, value in (explicit.comparison or {}).items():
        comparison.setdefault(key, value)
    if comparison.get("current_value") and comparison.get("reference_value"):
        comparison.setdefault("operand_unit", claim.unit or "")
    recovered = claim.model_copy(update={
        "comparison": comparison or claim.comparison,
        "parse_status": "AUTO_OK", "parse_reason": None,
    })
    decision = assess_claim_contract(recovered)
    if decision.status == "HOLD":
        return recovered.model_copy(update={"parse_status": "HOLD", "parse_reason": decision.reason_code})
    return recovered
