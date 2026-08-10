"""Deterministic execution for any CalculationPlan using official values only."""

from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from core.calculator import calculate
from core.kosis_fetcher import KosisValue
from schemas.evidence import CalculationPlan, EvidenceCellSchema


class OfficialValueLookup(Protocol):
    def fetch(self, cell: EvidenceCellSchema, *, article_date: date | None = None) -> KosisValue: ...


@dataclass(frozen=True, slots=True)
class CalculationExecutionResult:
    status: Literal["SUCCESS", "VALUE_UNAVAILABLE"]
    values: list[float]
    calculated_value: float | None
    snapshot_hashes: list[str]


def execute_calculation_plan(plan: CalculationPlan, fetcher: OfficialValueLookup, *, article_date: date | None) -> CalculationExecutionResult:
    """Fetch every confirmed evidence cell and calculate only with complete data."""
    results = [fetcher.fetch(cell, article_date=article_date) for cell in plan.required_cells]
    if any(result.status != "SUCCESS" or result.value is None for result in results):
        return CalculationExecutionResult("VALUE_UNAVAILABLE", [], None, [result.snapshot_hash for result in results])
    values = [float(result.value) for result in results]
    return CalculationExecutionResult("SUCCESS", values, calculate(plan, values), [result.snapshot_hash for result in results])
