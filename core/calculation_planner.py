"""Create deterministic multi-cell calculation plans from confirmed coordinates."""

from core.calculation_planner_impl import *  # noqa: F403
from core.calculation_planner_impl import build_calculation_plan as _build
from schemas.evidence import CalculationPlan


def build_calculation_plan(claim, current, candidate=None):
    if (
        claim.calculation == "DIFFERENCE"
        and candidate is not None
        and current.tbl_id == "DT_1B80A13"
        and any(value.strip() == "80대" for value in (claim.dimension or {}).values())
    ):
        age_axis = "YRE"
        members = candidate.dimension_member_codes.get(age_axis, {})
        required = (("80 - 84세", "360"), ("85 - 89세", "380"))
        if any(members.get(name) != code for name, code in required):
            return None
        current_cells = [_age_cell(current, age_axis, name, code, current.prd_de) for name, code in required]
        prior_period = _previous_year(current.prd_de)
        if prior_period is None:
            return None
        prior_cells = [_age_cell(current, age_axis, name, code, prior_period) for name, code in required]
        return CalculationPlan(calculation_type="SUM_DIFFERENCE", required_cells=[*current_cells, *prior_cells])
    return _build(claim, current, candidate)


def _previous_year(period: str) -> str | None:
    return str(int(period) - 1) if len(period) == 4 and period.isdigit() else None


def _age_cell(cell, axis: str, member: str, code: str, period: str):
    dimensions = dict(cell.dimension_members)
    codes = dict(cell.dimension_codes)
    old_member = dimensions.get(axis)
    dimensions[axis] = member
    codes[axis] = code
    key = cell.canonical_key
    if old_member:
        key = key.replace(f"{axis}:{old_member}", f"{axis}:{member}")
    key = key.replace(f"PRD_DE={cell.prd_de}", f"PRD_DE={period}")
    return cell.model_copy(update={
        "dimension_members": dimensions, "dimension_codes": codes,
        "prd_de": period, "canonical_key": key,
    })
