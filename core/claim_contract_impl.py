"""Executable AUTO-admission contract for canonical numerical Claims."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.unit_normalizer import compatible_units
from schemas.claim import ClaimSchema


SUPPORTED_CALCULATIONS = frozenset({
    "DIRECT_VALUE",
    "GROWTH_RATE",
    "DIFFERENCE",
    "SHARE",
    "RATIO",
    "MULTIPLE",
    "RANK",
    "THRESHOLD",
    "RECORD_HIGH",
    "RECORD_LOW",
})

_COMMON_REQUIRED_SLOTS = (
    "indicator",
    "value",
    "unit",
    "time",
    "calculation",
)
_SUPPORTED_PERIOD_COMPARISONS = {
    "YEAR_OVER_YEAR",
    "MONTH_OVER_MONTH",
    "QUARTER_OVER_QUARTER",
}


@dataclass(frozen=True, slots=True)
class ClaimContractDecision:
    """A non-mutating decision about whether a Claim may enter AUTO processing."""

    status: Literal["PASS", "HOLD"]
    reason_code: str | None = None
    missing_slots: tuple[str, ...] = ()
    detail: str | None = None


def assess_claim_contract(claim: ClaimSchema) -> ClaimContractDecision:
    """Apply common and calculation-specific AUTO admission requirements."""
    if claim.parse_status != "AUTO_OK":
        return ClaimContractDecision(status="PASS")

    missing_slots = tuple(
        slot for slot in _COMMON_REQUIRED_SLOTS if _is_missing(getattr(claim, slot))
    )
    if missing_slots:
        return _missing(missing_slots)

    calculation = str(claim.calculation).strip().upper()
    if calculation not in SUPPORTED_CALCULATIONS:
        return ClaimContractDecision(
            status="HOLD",
            reason_code="CLAIM_CALCULATION_UNSUPPORTED",
            detail=calculation,
        )
    if calculation == "GROWTH_RATE":
        return _assess_growth_rate(claim)
    if calculation == "DIFFERENCE":
        return _assess_difference(claim)
    if calculation == "SHARE":
        return _assess_share(claim)
    if calculation in {"RATIO", "MULTIPLE"}:
        return _assess_ratio_family(claim)
    if calculation == "RANK":
        return _assess_rank(claim)
    if calculation == "THRESHOLD":
        return _assess_threshold(claim)
    if calculation in {"RECORD_HIGH", "RECORD_LOW"}:
        comparison_type = str((claim.comparison or {}).get("type", "")).strip().upper()
        if comparison_type != calculation:
            return ClaimContractDecision(
                status="HOLD",
                reason_code="CLAIM_COMPARISON_UNSUPPORTED",
                detail=comparison_type,
            )
    return ClaimContractDecision(status="PASS")


def _assess_share(claim: ClaimSchema) -> ClaimContractDecision:
    if not compatible_units(claim.unit or "", "%"):
        return ClaimContractDecision(
            status="HOLD", reason_code="CLAIM_UNIT_INCOMPATIBLE", detail=claim.unit
        )
    comparison = claim.comparison
    if not comparison or str(comparison.get("type", "")).strip().upper() not in {
        "SHARE_OF_TOTAL", "PART_TO_WHOLE"
    }:
        return _missing(("comparison",))
    if any(_is_missing(comparison.get(field)) for field in ("numerator", "denominator")):
        return _missing(("comparison",))
    return ClaimContractDecision(status="PASS")


def _assess_ratio_family(claim: ClaimSchema) -> ClaimContractDecision:
    comparison = claim.comparison
    if not comparison or any(
        _is_missing(comparison.get(field)) for field in ("numerator", "denominator")
    ):
        return _missing(("comparison",))
    return ClaimContractDecision(status="PASS")


def _assess_rank(claim: ClaimSchema) -> ClaimContractDecision:
    if not claim.dimension or len(claim.dimension) != 1:
        return _missing(("dimension",))
    if (claim.unit or "").strip() != "위":
        return ClaimContractDecision(
            status="HOLD", reason_code="CLAIM_UNIT_INCOMPATIBLE", detail=claim.unit
        )
    if claim.value is None or claim.value <= 0 or not float(claim.value).is_integer():
        return ClaimContractDecision(
            status="HOLD", reason_code="CLAIM_TYPE_CONTRACT_INVALID", detail="rank_value"
        )
    condition = claim.condition
    required = ("rank_value", "order", "population_scope")
    if not condition or any(_is_missing(condition.get(field)) for field in required):
        return _missing(("condition",))
    try:
        rank_value = float(condition["rank_value"])
    except ValueError:
        return ClaimContractDecision(
            status="HOLD", reason_code="CLAIM_TYPE_CONTRACT_INVALID", detail="rank_value"
        )
    if rank_value != claim.value or str(condition["order"]).strip().upper() not in {
        "ASC", "DESC"
    }:
        return ClaimContractDecision(
            status="HOLD", reason_code="CLAIM_TYPE_CONTRACT_INVALID", detail="rank_contract"
        )
    return ClaimContractDecision(status="PASS")


def _assess_threshold(claim: ClaimSchema) -> ClaimContractDecision:
    condition = claim.condition
    required = ("operator", "threshold_value", "threshold_unit")
    if not condition or any(_is_missing(condition.get(field)) for field in required):
        return _missing(("condition",))
    operator = str(condition["operator"]).strip().upper()
    if operator not in {"GT", "GTE", "LT", "LTE"}:
        return ClaimContractDecision(
            status="HOLD", reason_code="CLAIM_TYPE_CONTRACT_INVALID", detail=operator
        )
    try:
        float(condition["threshold_value"].replace(",", ""))
    except ValueError:
        return ClaimContractDecision(
            status="HOLD", reason_code="CLAIM_TYPE_CONTRACT_INVALID", detail="threshold_value"
        )
    threshold_unit = condition["threshold_unit"]
    if not compatible_units(claim.unit or "", threshold_unit):
        return ClaimContractDecision(
            status="HOLD", reason_code="CLAIM_UNIT_INCOMPATIBLE", detail=threshold_unit
        )
    return ClaimContractDecision(status="PASS")

def _assess_growth_rate(claim: ClaimSchema) -> ClaimContractDecision:
    if not compatible_units(claim.unit or "", "%"):
        return ClaimContractDecision(
            status="HOLD", reason_code="CLAIM_UNIT_INCOMPATIBLE", detail=claim.unit
        )
    comparison_issue = _period_comparison_contract(
        claim.comparison, require_operands=False
    )
    if comparison_issue is not None:
        return comparison_issue
    return _direction_contract(claim.condition)


def _assess_difference(claim: ClaimSchema) -> ClaimContractDecision:
    comparison_issue = _period_comparison_contract(
        claim.comparison, require_operands=True
    )
    if comparison_issue is not None:
        return comparison_issue
    return _direction_contract(claim.condition)


def _period_comparison_contract(
    comparison: dict[str, str] | None, *, require_operands: bool
) -> ClaimContractDecision | None:
    if not comparison or _is_missing(comparison.get("type")):
        return _missing(("comparison",))
    comparison_type = str(comparison["type"]).strip().upper()
    if comparison_type not in _SUPPORTED_PERIOD_COMPARISONS:
        return ClaimContractDecision(
            status="HOLD",
            reason_code="CLAIM_COMPARISON_UNSUPPORTED",
            detail=comparison_type,
        )
    if require_operands and any(
        _is_missing(comparison.get(field))
        for field in ("current_value", "reference_value", "operand_unit")
    ):
        return _missing(("comparison",))
    return None


def _direction_contract(
    condition: dict[str, str] | None,
) -> ClaimContractDecision:
    if not condition or _is_missing(condition.get("direction")):
        return _missing(("condition",))
    direction = str(condition["direction"]).strip().upper()
    if direction not in {"INCREASE", "DECREASE"}:
        return ClaimContractDecision(
            status="HOLD",
            reason_code="CLAIM_TYPE_CONTRACT_INVALID",
            detail=direction,
        )
    return ClaimContractDecision(status="PASS")


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def _missing(slots: tuple[str, ...]) -> ClaimContractDecision:
    return ClaimContractDecision(
        status="HOLD",
        reason_code=f"MISSING_REQUIRED_SLOTS:{','.join(slots)}",
        missing_slots=slots,
    )
