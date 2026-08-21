"""Provenance contract for official-author release evidence.

This contract intentionally contains no extracted numeric value and no model
output fields. Values and verdicts remain the responsibility of deterministic
adapters and calculators.
"""

from datetime import date
import re
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


_SHA256_DOCUMENT_HASH = re.compile(r"^sha256:[0-9a-fA-F]{64}$")


class OfficialAuthorEvidenceSchema(BaseModel):
    """Auditable provenance for a value located in an official release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: Literal["OFFICIAL_AUTHOR_RELEASE"] = "OFFICIAL_AUTHOR_RELEASE"
    source_url: str = Field(min_length=1)
    published_at: date
    document_hash: str = Field(min_length=1)
    extraction_snippet: str = Field(min_length=1)
    extraction_context: str = Field(min_length=1)

    @field_validator("source_url")
    @classmethod
    def require_https_source_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTPS URL")
        return value

    @field_validator("document_hash")
    @classmethod
    def require_sha256_document_hash(cls, value: str) -> str:
        if not _SHA256_DOCUMENT_HASH.fullmatch(value):
            raise ValueError("document_hash must be sha256:<64 hexadecimal characters>")
        return value