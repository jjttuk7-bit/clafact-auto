"""Create deterministic multi-cell calculation plans from confirmed coordinates."""

import re

from core.comparison_normalizer import normalize_comparison
from core.record_periods import enumerate_record_periods
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import CalculationPlan, EvidenceCellSchema


def build_calculation_plan(
    claim: ClaimSchema,
    current: EvidenceCellSchema,
    candidate: KosisCandidateSchema | None = None,
) -> CalculationPlan | None:
    """Build a plan only when every official Evidence operand is explicit."""
    comparison = normalize_comparison(claim.comparison)
    calculation = claim.calculation
    if calculation is None and comparison and _is_year_over_year(comparison):
        calculation = "GROWTH_RATE"
    calculation = calculation or "DIRECT_VALUE"
    if calculation == "DIRECT_VALUE":
        return CalculationPlan(calculation_type="DIRECT_VALUE", required_cells=[current])
    if calculation in {"RECORD_HIGH", "RECORD_LOW"}:
        periods = enumerate_record_periods(
            candidate.start_period if candidate else None,
            current.prd_de,
            current.prd_se,
        )
        if periods is None:
            return None
        cells = [_period_cell(current, period) for period in periods]
        return CalculationPlan(calculation_type=calculation, required_cells=cells)
    if calculation in {"SHARE", "RATIO", "MULTIPLE"}:
        counterpart = _counterpart_cell(current, candidate, comparison)
        return CalculationPlan(calculation_type=calculation, required_cells=[current, counterpart]) if counterpart else None
    if calculation == "RANK":
        ranked = _rank_cells(current, candidate, claim.condition)
        return CalculationPlan(calculation_type="RANK", required_cells=ranked, operator=(claim.condition or {}).get("order")) if ranked else None
    if calculation == "THRESHOLD":
        condition = claim.condition or {}
        operator = str(condition.get("operator", "")).strip().upper()
        try:
            threshold = float(str(condition["threshold_value"]).replace(",", ""))
        except (KeyError, TypeError, ValueError):
            return None
        if operator not in {"GT", "GTE", "LT", "LTE"}:
            return None
        return CalculationPlan(calculation_type="THRESHOLD", required_cells=[current], literal_values=[threshold], operator=operator)
    if calculation in {"GROWTH_RATE", "DIFFERENCE"} and comparison:
        previous_period = _previous_comparison_period(current.prd_de, comparison)
        if previous_period is None:
            return None
        prior = current.model_copy(update={"prd_de": previous_period, "canonical_key": _with_period(current.canonical_key, current.prd_de, previous_period)})
        return CalculationPlan(calculation_type=calculation, required_cells=[current, prior])
    return None


def _counterpart_cell(
    current: EvidenceCellSchema,
    candidate: KosisCandidateSchema | None,
    comparison: dict[str, str] | None,
) -> EvidenceCellSchema | None:
    if candidate is None or not comparison:
        return None
    selector = str(comparison.get("denominator_member") or comparison.get("denominator") or "")
    if not selector:
        return None
    wants_total = any(token in selector.replace(" ", "") for token in ("전체", "총", "합계", "계"))
    choices: list[tuple[str, str]] = []
    for dimension_id, members in candidate.dimension_members.items():
        for member in members:
            if member == current.dimension_members.get(dimension_id):
                continue
            if (wants_total and _is_total_member(member)) or member.replace(" ", "") in selector.replace(" ", ""):
                choices.append((dimension_id, member))
    if len(choices) != 1:
        return None
    dimension_id, member = choices[0]
    code = candidate.dimension_member_codes.get(dimension_id, {}).get(member)
    if code is None:
        return None
    dimensions = dict(current.dimension_members)
    codes = dict(current.dimension_codes)
    previous = dimensions.get(dimension_id)
    dimensions[dimension_id] = member
    codes[dimension_id] = code
    key = current.canonical_key.replace(f"{dimension_id}:{previous}", f"{dimension_id}:{member}")
    if key == current.canonical_key and current.obj_id == dimension_id and current.member_code:
        key = key.replace(f"|MEMBER={current.member_code}|", f"|MEMBER={member}|")
    if key == current.canonical_key:
        key = f"{key}|DIMS={dimension_id}:{member}"
    return current.model_copy(update={
        "member_code": member if current.obj_id == dimension_id else current.member_code,
        "dimension_members": dimensions,
        "dimension_codes": codes,
        "canonical_key": key,
    })

def _is_total_member(member: str) -> bool:
    return member.replace(" ", "") in {"계", "전체", "합계", "총계", "전국"}

def _is_year_over_year(comparison: dict[str, str]) -> bool:
    values = {str(value).replace(" ", "").replace("_", "").upper() for value in comparison.values()}
    return bool(values & {"YEAROVERYEAR", "YEAR_OVER_YEAR", "YEAROVERYEAR", "전년동월대비", "전년대비", "전년"})
def _previous_comparison_period(period: str, comparison: dict[str, str]) -> str | None:
    if _is_year_over_year(comparison):
        return _previous_year_same_period(period)
    values = {str(value).replace(" ", "").replace("_", "").upper() for value in comparison.values()}
    if values.intersection({"MONTHOVERMONTH", "전월대비", "전월비", "전월"}):
        monthly = re.fullmatch(r"(\d{4})-?(\d{2})", period)
        if monthly is None:
            return None
        year, month = int(monthly.group(1)), int(monthly.group(2))
        previous_year, previous_month = (year - 1, 12) if month == 1 else (year, month - 1)
        separator = "-" if "-" in period else ""
        return f"{previous_year:04d}{separator}{previous_month:02d}"

    if not values.intersection({"QUARTEROVERQUARTER", "QUARTER_OVER_QUARTER", "전분기대비", "전분기비", "전분기"}):
        return None
    quarterly = re.fullmatch(r"(\d{4})-Q([1-4])", period, re.IGNORECASE)
    if quarterly is None:
        return None
    year, quarter = int(quarterly.group(1)), int(quarterly.group(2))
    previous_year, previous_quarter = (year - 1, 4) if quarter == 1 else (year, quarter - 1)
    return f"{previous_year:04d}-Q{previous_quarter}"

def _previous_year_same_period(period: str) -> str | None:
    quarterly = re.fullmatch(r"(\d{4})-Q([1-4])", period, re.IGNORECASE)
    if quarterly:
        return f"{int(quarterly.group(1)) - 1:04d}-Q{quarterly.group(2)}"
    normalized = period.replace("-", "")
    if len(normalized) == 4 and normalized.isdigit():
        return f"{int(normalized) - 1:04d}"
    if len(normalized) != 6 or not normalized.isdigit():
        return None
    separator = "-" if "-" in period else ""
    return f"{int(normalized[:4]) - 1:04d}{separator}{normalized[4:]}"


def _with_period(key: str, current: str, prior: str) -> str:
    return key.replace(current, prior) if current in key else f"{key}|PRD_DE={prior}"


def _period_cell(current: EvidenceCellSchema, period: str) -> EvidenceCellSchema:
    return current.model_copy(update={
        "prd_de": period,
        "canonical_key": _with_period(current.canonical_key, current.prd_de, period),
    })


def _rank_cells(
    current: EvidenceCellSchema,
    candidate: KosisCandidateSchema | None,
    condition: dict[str, str] | None,
) -> list[EvidenceCellSchema] | None:
    if candidate is None:
        return None
    requested_axis = str((condition or {}).get("rank_axis") or "").replace("별", "")
    choices = [
        dimension_id for index, dimension_id in enumerate(candidate.dimension_ids)
        if (not requested_axis or requested_axis in candidate.dimension_names[index].replace("별", ""))
        and current.dimension_members.get(dimension_id) in candidate.dimension_members.get(dimension_id, [])
    ]
    if len(choices) != 1:
        return None
    dimension_id = choices[0]
    members = [member for member in candidate.dimension_members[dimension_id] if not _is_total_member(member)]
    if current.dimension_members[dimension_id] not in members or len(members) < 2:
        return None
    cells = [current]
    for member in members:
        if member == current.dimension_members[dimension_id]:
            continue
        code = candidate.dimension_member_codes.get(dimension_id, {}).get(member)
        if code is None:
            return None
        dimensions = dict(current.dimension_members)
        codes = dict(current.dimension_codes)
        dimensions[dimension_id] = member
        codes[dimension_id] = code
        cells.append(current.model_copy(update={
            "dimension_members": dimensions,
            "dimension_codes": codes,
            "canonical_key": current.canonical_key.replace(f"{dimension_id}:{current.dimension_members[dimension_id]}", f"{dimension_id}:{member}"),
        }))
    return cells