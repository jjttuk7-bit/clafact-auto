"""Typed operator-review artifacts derived from immutable E2E results."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewQueueRecord(BaseModel):
    """One actionable Claim review item with preserved source provenance."""

    model_config = ConfigDict(extra="forbid")

    queue_type: Literal["parse", "concept", "catalog", "evidence", "publication_policy", "retry", "verification"]
    owner_role: str
    next_action: str
    route_status: Literal["HOLD", "HUMAN_REVIEW"]
    reason_code: str
    claim_id: str
    article_id: str
    sentence_id: str
    source_ref: str
    source_sentence: str
    slots: dict[str, Any] = Field(default_factory=dict)
    candidate_metadata: dict[str, Any] = Field(default_factory=dict)
