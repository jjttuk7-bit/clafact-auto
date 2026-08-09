"""Claim interpretation contract."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ClaimSchema(BaseModel):
    """A numerical claim represented through the 12 semantic slots."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    source_sentence: str
    indicator: str | None = None
    value: float | None = None
    unit: str | None = None
    time: str | None = None
    frequency: str | None = None
    region: str | None = None
    population: str | None = None
    dimension: dict[str, str] | None = None
    comparison: dict[str, str] | None = None
    calculation: str | None = None
    condition: dict[str, str] | None = None
    source_hint: str | None = None
    parse_status: Literal["AUTO_OK", "HOLD", "HUMAN_REVIEW"]
    parse_reason: str | None = None

