"""Resolve relative claim times from an article publication date."""

from datetime import date
import re


def resolve_relative_time(c, article_date: date | None):
    v = (c.time or "").strip()
    v = re.sub(r"\s*\(\s*1\s*[~～-]\s*3\s*월\s*\)\s*$", "", v)
    if v in {"올해", "금년"}:
        return _hold(c) if article_date is None else c.model_copy(update={"time": f"{article_date.year}년", "frequency": "년"})
    last_month = re.fullmatch(r"지난\s*(?P<month>\d{1,2})월", v)
    if last_month:
        if article_date is None:
            return _hold(c)
        month = int(last_month["month"])
        year = article_date.year if month <= article_date.month else article_date.year - 1
        return c.model_copy(update={"time": f"{year}년 {month}월", "frequency": "월"})
    month_match = re.fullmatch(r"(?P<year>올해|금년|지난해|작년|전년)\s*(?P<month>\d{1,2})월", v)
    if month_match:
        if article_date is None:
            return _hold(c)
        year = article_date.year - int(month_match["year"] in {"지난해", "작년", "전년"})
        return c.model_copy(update={"time": f"{year}년 {int(month_match['month'])}월", "frequency": "월"})
    named = re.fullmatch(r"(?P<year>올해|금년|지난해|작년|전년|지난)\s*(?P<period>[1-4]분기|상반기|하반기)", v)
    if named:
        if article_date is None:
            return _hold(c)
        previous = named["year"] in {"지난해", "작년", "전년"}
        period = named["period"]
        frequency = "분기" if period.endswith("분기") else "반기"
        return c.model_copy(update={"time": f"{article_date.year - int(previous)}년 {period}", "frequency": frequency})
    if v == "전년 동분기":
        if article_date is None:
            return _hold(c)
        explicit_target = re.search(r"(?:지난|올해|금년)\s*([1-4])분기", c.source_sentence)
        quarter = int(explicit_target.group(1)) if explicit_target else (article_date.month - 1) // 3 + 1
        return c.model_copy(update={"time": f"{article_date.year - 1}년 {quarter}분기", "frequency": "분기"})
    if v not in {"지난달", "전월", "이달", "당월", "지난해", "작년", "전년"}:
        return c
    if article_date is None:
        return _hold(c)
    if v in {"이달", "당월"}:
        return c.model_copy(update={"time": f"{article_date.year}년 {article_date.month}월", "frequency": "월"})
    if v in {"지난해", "작년", "전년"}:
        return c.model_copy(update={"time": f"{article_date.year - 1}년", "frequency": "년"})
    year, month = article_date.year, article_date.month - 1
    if month == 0:
        year, month = year - 1, 12
    return c.model_copy(update={"time": f"{year}년 {month}월", "frequency": "월"})


def _hold(c):
    return c.model_copy(update={"parse_status": "HOLD", "parse_reason": "ARTICLE_DATE_REQUIRED_FOR_RELATIVE_TIME"})
