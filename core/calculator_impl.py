"""Deterministic calculations over KOSIS official values."""

from schemas.evidence import CalculationPlan


def calculate(plan: CalculationPlan, values: list[float]) -> float:
    """Calculate supported operations with explicit cardinality checks."""
    if plan.calculation_type == "DIRECT_VALUE":
        _require(values, 1)
        return values[0]
    if plan.calculation_type == "RANK":
        if not values:
            raise ValueError("calculation requires at least 1 value")
        if (plan.operator or "DESC").upper() == "ASC":
            return float(1 + sum(value < values[0] for value in values[1:]))
        return float(1 + sum(value > values[0] for value in values[1:]))
    if plan.calculation_type in {"RECORD_HIGH", "RECORD_LOW"}:
        if not values:
            raise ValueError("calculation requires at least 1 value")
        if plan.calculation_type == "RECORD_HIGH":
            return max(values)
        return min(values)
    if plan.calculation_type == "SHARE":
        if len(values) < 2:
            raise ValueError("calculation requires at least 2 values")
        denominator = values[-1]
        if denominator == 0:
            raise ValueError("zero denominator is not allowed")
        return sum(values[:-1]) / denominator * 100

    _require(values, 2)
    numerator, denominator = values
    if plan.calculation_type == "DIFFERENCE":
        return numerator - denominator
    if plan.calculation_type == "THRESHOLD":
        operator = (plan.operator or "GTE").upper()
        comparisons = {"GT": numerator > denominator, "GTE": numerator >= denominator, "LT": numerator < denominator, "LTE": numerator <= denominator}
        if operator not in comparisons:
            raise ValueError(f"Unsupported threshold operator: {operator}")
        return 1.0 if comparisons[operator] else 0.0
    if denominator == 0:
        raise ValueError("zero denominator is not allowed")
    if plan.calculation_type == "GROWTH_RATE":
        return (numerator - denominator) / denominator * 100
    if plan.calculation_type in {"RATIO", "MULTIPLE"}:
        return numerator / denominator
    raise ValueError(f"Unsupported calculation type: {plan.calculation_type}")


def _require(values: list[float], count: int) -> None:
    if len(values) != count:
        raise ValueError(f"calculation requires {count} values")
