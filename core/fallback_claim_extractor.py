"""Technical fallback boundary for OpenAI claim extraction."""

from __future__ import annotations

from datetime import date

from core.claim_parser import StructuredClaimExtractor
from core.openai_function_claim_extractor import (
    OpenAIContractError,
    OpenAITransientError,
)
from schemas.claim import ClaimSchema


class FallbackClaimExtractor:
    """Use HCX once only when OpenAI fails transiently or violates its contract."""

    def __init__(
        self,
        primary: StructuredClaimExtractor,
        fallback: StructuredClaimExtractor,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.last_provider = "unavailable"

    def extract(
        self, source_sentence: str, *, article_published_at: date | None = None, article_context: str | None = None
    ) -> ClaimSchema:
        self.last_provider = "unavailable"
        try:
            primary_kwargs = {"article_published_at": article_published_at}
            if article_context is not None:
                primary_kwargs["article_context"] = article_context
            claim = self.primary.extract(source_sentence, **primary_kwargs)
        except (OpenAITransientError, OpenAIContractError):
            claim = self.fallback.extract(source_sentence, article_published_at=article_published_at)
            self.last_provider = "hcx"
            return claim

        self.last_provider = "openai"
        return claim
