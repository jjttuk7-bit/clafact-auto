"""Durable source-provenance records for KOSIS verification claims."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.claim import ClaimSchema


class ClaimRegistryRecord(BaseModel):
    """One source sentence registered for future KOSIS claim verification."""

    model_config = ConfigDict(extra="forbid")

    article_id: str
    sentence_id: str
    article_published_at: date | None = None
    source_ref: str
    source_metadata: dict[str, str | None] = Field(default_factory=dict)
    claim: ClaimSchema
    review_status: Literal["UNREVIEWED", "IN_REVIEW", "APPROVED", "REJECTED"] = "UNREVIEWED"
