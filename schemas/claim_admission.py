"""Admission routing contract for numeric article candidates."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AdmissionLabel = Literal[
    "KOSIS_PIPELINE_ELIGIBLE",
    "CONTEXT_REQUIRED",
    "MULTI_CLAIM_SPLIT_REQUIRED",
    "NON_KOSIS_OR_PRIVATE",
    "FORECAST_OPINION_UNVERIFIABLE",
    "NOT_A_VERIFIABLE_CLAIM",
]


class AdmissionDecision(BaseModel):
    """A pre-official-query routing decision, never a verification verdict."""

    model_config = ConfigDict(extra="forbid")

    label: AdmissionLabel
    reason_code: str


class AdmissionEvent(BaseModel):
    """An auditable state transition while processing one source candidate."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    claim_id: str
    label: AdmissionLabel
    reason_code: str
    detail: str | None = None


class AdmissionRouteResult(BaseModel):
    """Output of admission processing before or instead of official verification."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    route_status: Literal["ADMISSION_ROUTED", "OFFICIAL_VERIFICATION_STARTED"]
    decision: AdmissionDecision
    events: list[AdmissionEvent] = Field(default_factory=list)
