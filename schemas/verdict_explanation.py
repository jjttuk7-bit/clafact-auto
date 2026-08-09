"""Presentation-only explanation contract for an already determined verdict."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VerdictExplanationSchema(BaseModel):
    """Natural-language explanation that cannot change the verification verdict."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["LLM", "TEMPLATE"]
    conclusion: Literal["일치", "불일치", "판정 불가"]
    summary: str = Field(min_length=1, max_length=300)
    detail: str = Field(min_length=1, max_length=500)
    next_action: str | None = Field(default=None, max_length=300)
