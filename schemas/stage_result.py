"""Durable result contract for one claim at one pipeline stage."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.pipeline_trace import PipelineStageName


StageExecutionStatus = Literal[
    "PASS",
    "REWORK",
    "HUMAN_REVIEW",
    "EXCLUDED",
    "HOLD",
    "FAILED",
    "SKIPPED",
]


class StageResultSchema(BaseModel):
    """One append-only stage attempt with reproducibility identifiers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_claim_id: str = Field(min_length=1)
    child_claim_id: str = Field(min_length=1)
    stage: PipelineStageName
    status: StageExecutionStatus
    reason_code: str | None = None
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_ref: str | None = None
    started_at: str = Field(min_length=1)
    finished_at: str = Field(min_length=1)
    code_version: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    attempt: int = Field(default=1, ge=1)

