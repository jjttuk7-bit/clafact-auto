import pytest

from core.calculator import calculate
from schemas.evidence import CalculationPlan


def _plan(kind: str) -> CalculationPlan:
    return CalculationPlan(calculation_type=kind, required_cells=[])


def test_record_high_returns_maximum_and_accepts_a_tie() -> None:
    assert calculate(_plan("RECORD_HIGH"), [100.0, 1419.0, 1419.0]) == 1419.0


def test_record_low_returns_minimum_and_accepts_a_tie() -> None:
    assert calculate(_plan("RECORD_LOW"), [8.0, 3.0, 3.0]) == 3.0


@pytest.mark.parametrize("kind", ["RECORD_HIGH", "RECORD_LOW"])
def test_record_calculation_rejects_empty_history(kind: str) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        calculate(_plan(kind), [])
