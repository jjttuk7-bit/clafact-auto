"""Normalized, source-grounded input contract for official KOSIS discovery."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class KosisQuerySpecSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    indicator: str | None = None
    measure_family: str
    value: float | None = None
    unit: str | None = None
    unit_family: str
    scale: float = 1.0
    period: str | None = None
    frequency: str | None = None
    period_mode: Literal["SINGLE", "CUMULATIVE", "UNRESOLVED"]
    region: str | None = None
    geography_scope: Literal["NATIONAL", "LOCAL", "COUNTRY", "UNRESOLVED"]
    population: str | None = None
    dimensions: dict[str, list[str]] = Field(default_factory=dict)
    calculation: str
    required_evidence_cells: int = 1
    official_route: Literal["KOSIS_FIRST"] = "KOSIS_FIRST"
    readiness_status: Literal["COORDINATE_READY", "PRE_VERIFICATION"]
    readiness_reasons: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
