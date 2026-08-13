"""Common Article → Claim Split → 12-slot parsing entrypoint."""

from __future__ import annotations

from datetime import date

from core.article_preprocessor import preprocess_article
from core.claim_parser import StructuredClaimExtractor, parse_claim
from schemas.claim import ClaimSchema


def parse_article_claims(
    article_text: str,
    extractor: StructuredClaimExtractor,
    *,
    article_published_at: date | None,
) -> list[ClaimSchema]:
    """Parse every numerical Claim candidate from one article or UI input."""
    candidates = preprocess_article(article_text).claim_candidates
    if not candidates and article_text.strip():
        candidates = [article_text.strip()]
    return [
        parse_claim(candidate, extractor, article_published_at=article_published_at)
        for candidate in candidates
    ]