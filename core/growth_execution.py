"""Deterministic execution of multi-cell growth plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from core.calculator import calculate
from core.kosis_fetcher import KosisValue
from schemas.evidence import CalculationPlan, EvidenceCellSchema


class OfficialValueLookup(Protocol):
    """Minimal read-only official-value dependency."""

    def fetch(self, cell: EvidenceCellSchema, *, article_date: date | None = None) -> KosisValue:
        """Fetch one already-confirmed official coordinate."""


@dataclass(frozen=True, slots=True)
class GrowthExecutionResult:
    """Auditable outcome of a deterministic two-value calculation."""

    status: Literal["SUCCESS", "VALUE_UNAVAILABLE"]
    values: list[float]
    calculated_value: float | None


def execute_growth_plan(
    plan: CalculationPlan,
    fetcher: OfficialValueLookup,
    article_date: date,
) -> GrowthExecutionResult:
    """Fetch confirmed cells and calculate only when every official value is available."""
    if plan.calculation_type != "GROWTH_RATE" or len(plan.required_cells) != 2:
        raise ValueError("GROWTH_RATE_TWO_CELLS_REQUIRED")
    results = [fetcher.fetch(cell, article_date=article_date) for cell in plan.required_cells]
    if any(result.status != "SUCCESS" or result.value is None for result in results):
        return GrowthExecutionResult("VALUE_UNAVAILABLE", [], None)
    values = [float(result.value) for result in results]
    return GrowthExecutionResult("SUCCESS", values, calculate(plan, values))
