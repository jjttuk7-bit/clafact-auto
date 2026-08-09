"""Resolve relative claim times only when an article publication date is available."""

from __future__ import annotations

from datetime import date

from schemas.claim import ClaimSchema


def resolve_relative_time(claim: ClaimSchema, article_date: date | None) -> ClaimSchema:
    """Turn an explicit Korean previous-month reference into an absolute monthly slot."""
    if article_date is None or claim.time not in {"지난달", "전월"}:
        return claim
    year, month = article_date.year, article_date.month - 1
    if month == 0:
        year, month = year - 1, 12
    return claim.model_copy(update={"time": f"{year}년 {month}월", "frequency": "월"})