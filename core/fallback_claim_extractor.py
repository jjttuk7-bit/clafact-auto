"""Technical fallback boundary for OpenAI claim extraction."""

from __future__ import annotations

from datetime import date

from core.claim_parser import StructuredClaimExtractor
from core.openai_function_claim_extractor import (
    OpenAIContractError,
    OpenAITransientError,
)
from schemas.claim import ClaimSchema
from schemas.claim_group import ClaimGroupingPlan, NumericMention


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
        self, source_sentence: str, *, article_published_at: date | None = None
    ) -> ClaimSchema:
        self.last_provider = "unavailable"
        try:
            claim = self.primary.extract(source_sentence, article_published_at=article_published_at)
        except (OpenAITransientError, OpenAIContractError):
            claim = self.fallback.extract(source_sentence, article_published_at=article_published_at)
            self.last_provider = "hcx"
            return claim

        self.last_provider = "openai"
        return claim

    def group_claims(
        self,
        source_sentence: str,
        mentions: list[NumericMention],
    ) -> ClaimGroupingPlan:
        self.last_provider = "unavailable"
        try:
            plan = self.primary.group_claims(source_sentence, mentions)  # type: ignore[attr-defined]
        except (OpenAITransientError, OpenAIContractError):
            plan = self.fallback.group_claims(  # type: ignore[attr-defined]
                source_sentence,
                mentions,
            )
            self.last_provider = "hcx"
            return plan

        self.last_provider = "openai"
        return plan
