"""Contracts for registered non-KOSIS official-author evidence."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class OfficialAuthorDocumentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_period: str
    source_url: str
    value_pattern: str
    period_patterns: list[str] = Field(default_factory=list)
    unit: str
    scale: float = 1.0
    publication_date_pattern: str


class OfficialAuthorProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    author_name: str
    indicator_terms: list[str] = Field(min_length=1)
    source_hint_terms: list[str] = Field(default_factory=list)
    trusted_hosts: list[str] = Field(min_length=1)
    documents: list[OfficialAuthorDocumentProfile] = Field(default_factory=list)


class OfficialAuthorEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    author_name: str
    profile_id: str
    reference_period: str | None = None
    official_value: float | None = None
    unit: str | None = None
    published_at: date | None = None
    source_url: str = ""
    retrieved_at: str = ""
    content_hash: str = ""
    reason_code: str | None = None
