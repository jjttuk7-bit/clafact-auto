import pytest

from core.calculator import calculate
from schemas.evidence import CalculationPlan


def plan(kind: str) -> CalculationPlan:
    return CalculationPlan(calculation_type=kind, required_cells=[])


def test_calculate_direct_value() -> None:
    assert calculate(plan("DIRECT_VALUE"), [70.0]) == 70.0


def test_calculate_difference() -> None:
    assert calculate(plan("DIFFERENCE"), [75.0, 70.0]) == 5.0


def test_calculate_growth_rate() -> None:
    assert calculate(plan("GROWTH_RATE"), [110.0, 100.0]) == 10.0


def test_calculate_ratio() -> None:
    assert calculate(plan("RATIO"), [25.0, 100.0]) == 0.25


def test_calculate_rejects_zero_denominator() -> None:
    with pytest.raises(ValueError, match="zero"):
        calculate(plan("RATIO"), [1.0, 0.0])


def test_calculate_rejects_wrong_value_count() -> None:
    with pytest.raises(ValueError, match="requires 2"):
        calculate(plan("DIFFERENCE"), [1.0])


def test_calculate_share_from_two_parts_and_total() -> None:
    assert round(calculate(plan("SHARE"), [15943.0, 25841.0, 87115.0]), 3) == 47.964


def test_calculate_rank_returns_one_for_largest_first_value() -> None:
    assert calculate(plan("RANK"), [9.193, 8.708]) == 1.0


def test_calculate_multiple() -> None:
    assert calculate(plan("MULTIPLE"), [7.5, 3.1]) == 7.5 / 3.1


def test_calculate_threshold_returns_one_when_value_meets_threshold() -> None:
    assert calculate(plan("THRESHOLD"), [70.0, 70.0]) == 1.0


def test_calculate_threshold_returns_zero_when_value_is_below_threshold() -> None:
    assert calculate(plan("THRESHOLD"), [69.9, 70.0]) == 0.0


def test_calculate_rank_honors_ascending_order() -> None:
    assert calculate(CalculationPlan(calculation_type="RANK", required_cells=[], operator="ASC"), [3.0, 2.0, 4.0]) == 2.0


def test_calculate_threshold_honors_strict_operator() -> None:
    assert calculate(CalculationPlan(calculation_type="THRESHOLD", required_cells=[], operator="GT"), [4.0, 4.0]) == 0.0