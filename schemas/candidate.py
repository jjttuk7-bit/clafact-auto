"""KOSIS catalog candidates and retrieval-stage decisions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KosisPeriodRangeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_period: str | None = None
    end_period: str | None = None


class KosisCandidateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: str
    tbl_id: str
    tbl_name: str
    core_item_ids: list[str] = Field(default_factory=list)
    core_item_names: list[str] = Field(default_factory=list)
    dimension_ids: list[str] = Field(default_factory=list)
    dimension_names: list[str] = Field(default_factory=list)
    dimension_members: dict[str, list[str]] = Field(default_factory=dict)
    dimension_member_codes: dict[str, dict[str, str]] = Field(default_factory=dict)
    unit_names: list[str] = Field(default_factory=list)
    item_units: dict[str, str] = Field(default_factory=dict)
    frequency: str | None = None
    start_period: str | None = None
    end_period: str | None = None
    period_ranges: dict[str, KosisPeriodRangeSchema] = Field(default_factory=dict)
    source_stat_id: str | None = None
    source_name: str | None = None
    binding_scope_terms: list[str] = Field(default_factory=list)
    metadata_status: str


class HardGuardResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    reject_codes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_tbl_id: str
    semantic_score: float
    top1_top2_margin: float | None = None
    route_status: Literal["AUTO", "HOLD", "HUMAN_REVIEW"]
    reason_code: str | None = None

