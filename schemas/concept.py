"""Semantic-standard mapping contract."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StandardConceptSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str
    canonical_name: str
    standard_key: str
    matched_alias: str | None = None
    status: Literal["MATCHED", "NEW_CANDIDATE", "UNRESOLVED"]

