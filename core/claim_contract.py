"""Executable AUTO-admission contract for canonical numerical Claims."""

from core import claim_contract_impl as _impl
from core.claim_contract_impl import ClaimContractDecision, SUPPORTED_CALCULATIONS
from schemas.claim import ClaimSchema

__all__ = ["SUPPORTED_CALCULATIONS", "ClaimContractDecision", "assess_claim_contract"]


def assess_claim_contract(claim: ClaimSchema) -> ClaimContractDecision:
    """Permit deferred operands only when deterministic official evidence supplies them."""
    if str(claim.calculation or "").strip().upper() != "DIFFERENCE":
        return _impl.assess_claim_contract(claim)
    comparison = claim.comparison or {}
    if comparison.get("operand_source") != "OFFICIAL_EVIDENCE":
        return _impl.assess_claim_contract(claim)
    if claim.parse_status != "AUTO_OK":
        return ClaimContractDecision(status="PASS")
    missing = tuple(
        slot for slot in _impl._COMMON_REQUIRED_SLOTS
        if _impl._is_missing(getattr(claim, slot))
    )
    if missing:
        return _impl._missing(missing)
    comparison_issue = _impl._period_comparison_contract(
        claim.comparison, require_operands=False
    )
    if comparison_issue is not None:
        return comparison_issue
    return _impl._direction_contract(claim.condition)
