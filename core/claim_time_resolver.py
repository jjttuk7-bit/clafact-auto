"""Resolve relative claim times only when an article publication date is available."""

from __future__ import annotations

from datetime import date
import re

from schemas.claim import ClaimSchema


def resolve_relative_time(claim: ClaimSchema, article_date: date | None) -> ClaimSchema:
    """Resolve an explicit relative target period from the article publication date."""
    relative_time = (claim.time or "").strip()
    named_period = re.fullmatch(
        r"(?P<year>올해|금년|지난해|작년|전년)\s*(?P<period>[1-4]분기|상반기|하반기)",
        relative_time,
    )
    if named_period is not None:
        if article_date is None:
            return claim.model_copy(
                update={
                    "parse_status": "HOLD",
                    "parse_reason": "ARTICLE_DATE_REQUIRED_FOR_RELATIVE_TIME",
                }
            )
        year = article_date.year
        if named_period["year"] in {"지난해", "작년", "전년"}:
            year -= 1
        period = named_period["period"]
        frequency = "분기" if period.endswith("분기") else "반기"
        update = {"time": f"{year}년 {period}", "frequency": frequency}
        if frequency == "반기":
            update.update(
                {
                    "parse_status": "HOLD",
                    "parse_reason": "KOSIS_HALF_YEAR_PERIOD_UNSUPPORTED",
                }
            )
        return claim.model_copy(update=update)
    if relative_time in {"올해", "금년"}:
        if article_date is None:
            return claim.model_copy(update={"parse_status": "HOLD", "parse_reason": "ARTICLE_DATE_REQUIRED_FOR_RELATIVE_TIME"})
        return claim.model_copy(update={"time": f"{article_date.year}년", "frequency": "년"})
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
