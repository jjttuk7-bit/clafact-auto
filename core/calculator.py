"""Deterministic calculations over KOSIS official values."""

from core.calculator_impl import calculate as _calculate
from schemas.evidence import CalculationPlan


def calculate(plan: CalculationPlan, values: list[float]) -> float:
    if plan.calculation_type == "SUM_DIFFERENCE":
        if len(values) != 4:
            raise ValueError("calculation requires 4 values")
        return sum(values[:2]) - sum(values[2:])
    return _calculate(plan, values)
