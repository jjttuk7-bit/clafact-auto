"""Create deterministic multi-cell calculation plans from confirmed coordinates."""

from schemas.claim import ClaimSchema
from schemas.evidence import CalculationPlan, EvidenceCellSchema


def build_calculation_plan(claim: ClaimSchema, current: EvidenceCellSchema) -> CalculationPlan | None:
    """Build a plan only for explicit supported calculations and period relations."""
    calculation = claim.calculation
    if calculation is None and claim.comparison and claim.comparison.get("basis") == "전년 동월 대비":
        calculation = "GROWTH_RATE"
    if calculation == "DIRECT_VALUE":
        return CalculationPlan(calculation_type="DIRECT_VALUE", required_cells=[current])
    if calculation == "GROWTH_RATE" and claim.comparison and claim.comparison.get("basis") == "전년 동월 대비":
        previous_period = _previous_year_same_period(current.prd_de)
        if previous_period is None:
            return None
        prior = current.model_copy(update={"prd_de": previous_period, "canonical_key": _with_period(current.canonical_key, current.prd_de, previous_period)})
        return CalculationPlan(calculation_type="GROWTH_RATE", required_cells=[current, prior])
    return None


def _previous_year_same_period(period: str) -> str | None:
    normalized = period.replace("-", "")
    if len(normalized) != 6 or not normalized.isdigit():
        return None
    return f"{int(normalized[:4]) - 1:04d}{normalized[4:]}"


def _with_period(key: str, current: str, prior: str) -> str:
    return key.replace(current, prior) if current in key else f"{key}|PRD_DE={prior}"