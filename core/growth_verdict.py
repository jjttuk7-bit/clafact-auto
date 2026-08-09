"""Verdict integration for registered multi-cell CPI growth claims."""

from __future__ import annotations

from datetime import date

from core.cpi_growth_resolver import resolve_cpi_growth_plan
from core.growth_execution import OfficialValueLookup, execute_growth_plan
from core.verdict_engine import make_verdict
from schemas.claim import ClaimSchema
from schemas.verdict import VerdictSchema


def make_cpi_growth_verdict(
    claim: ClaimSchema,
    article_date: date,
    fetcher: OfficialValueLookup,
) -> VerdictSchema | None:
    """Create a verdict from two registered official CPI index cells, if applicable."""
    plan = resolve_cpi_growth_plan(claim)
    if plan is None:
        return None
    execution = execute_growth_plan(plan.calculation_plan, fetcher, article_date)
    verdict = make_verdict(
        claim.claim_id,
        claim.value,
        execution.values,
        execution.calculated_value,
        tolerance=0.05,
    )
    return verdict.model_copy(
        update={
            "evidence_cells": plan.calculation_plan.required_cells,
            "dataset_version": plan.dataset_version,
            "calculation_version": "1.0",
        }
    )
