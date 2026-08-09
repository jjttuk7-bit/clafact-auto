"""Auditable per-claim pipeline execution contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PipelineStageName = Literal[
    "PREPROCESS",
    "SENTENCE_SPLIT",
    "CLAIM_CANDIDATE_SELECTION",
    "CLAIM_SPLIT",
    "CLAIM_PARSE",
    "SEMANTIC_MAPPING",
    "CATALOG_SEARCH",
    "HARD_GUARD",
    "SEMANTIC_MATCH",
    "EVIDENCE_CELL",
    "OFFICIAL_VALUE_FETCH",
    "CALCULATION",
    "VERDICT",
]


class PipelineTraceEvent(BaseModel):
    """One deterministic stage result without exposing secret inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: PipelineStageName
    status: Literal["PASS", "HOLD", "HUMAN_REVIEW", "SKIPPED"]
    reason_code: str | None = None
    output_ref: str | None = None


class PipelineTraceSchema(BaseModel):
    """Versioned execution trace retained with a claim result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    route_status: Literal["AUTO", "HOLD", "HUMAN_REVIEW"] = "AUTO"
    events: list[PipelineTraceEvent] = Field(default_factory=list)
    preprocess_version: str
    claim_schema_version: str
    semantic_standard_version: str = "1.0"
    kosis_catalog_version: str = "1.0"
    matching_version: str = "1.0"
    calculation_version: str = "1.0"

    def pass_stage(self, stage: PipelineStageName, *, output_ref: str | None = None) -> "PipelineTraceSchema":
        event = PipelineTraceEvent(stage=stage, status="PASS", output_ref=output_ref)
        return self.model_copy(update={"events": [*self.events, event]})

    def hold(self, stage: PipelineStageName, reason_code: str) -> "PipelineTraceSchema":
        event = PipelineTraceEvent(stage=stage, status="HOLD", reason_code=reason_code)
        return self.model_copy(update={"route_status": "HOLD", "events": [*self.events, event]})

    def human_review(self, stage: PipelineStageName, reason_code: str) -> "PipelineTraceSchema":
        event = PipelineTraceEvent(stage=stage, status="HUMAN_REVIEW", reason_code=reason_code)
        return self.model_copy(update={"route_status": "HUMAN_REVIEW", "events": [*self.events, event]})