"""Resolve relative claim times only when an article publication date is available."""

from __future__ import annotations

from datetime import date

from schemas.claim import ClaimSchema


def resolve_relative_time(claim: ClaimSchema, article_date: date | None) -> ClaimSchema:
    """Resolve an explicit relative target period from the article publication date."""
    relative_time = (claim.time or "").strip()
    if relative_time not in {"지난달", "전월", "이달", "당월", "작년", "전년"}:
        return claim
    if article_date is None:
        return claim.model_copy(update={"parse_status": "HOLD", "parse_reason": "ARTICLE_DATE_REQUIRED_FOR_RELATIVE_TIME"})
    if relative_time in {"이달", "당월"}:
        return claim.model_copy(update={"time": f"{article_date.year}년 {article_date.month}월", "frequency": "월"})
    if relative_time in {"작년", "전년"}:
        return claim.model_copy(update={"time": f"{article_date.year - 1}년", "frequency": "년"})
    year, month = article_date.year, article_date.month - 1
    if month == 0:
        year, month = year - 1, 12
    return claim.model_copy(update={"time": f"{year}년 {month}월", "frequency": "월"})
