"""Resolve relative claim times from an article publication date."""

from datetime import date
import re


def resolve_relative_time(c, article_date: date | None):
    c = _normalize_explicit_frequency(c)
    v = (c.time or "").strip()
    reporting_month = _resolve_source_reporting_month(c, article_date)
    if reporting_month is not c:
        return reporting_month
    if not v:
        return _resolve_source_previous_month(c, article_date)
    v = re.sub(r"\s*\(\s*1\s*[~～-]\s*3\s*월\s*\)\s*$", "", v)
    first_month = re.fullmatch(r"(?P<year>올해|금년|지난해|작년|전년)\s*첫\s*달", v)
    if first_month:
        if article_date is None:
            return _hold(c)
        year = article_date.year - int(first_month["year"] in {"지난해", "작년", "전년"})
        return c.model_copy(update={"time": f"{year}년 1월", "frequency": "월"})
    if v in {"올해", "금년"}:
        return _hold(c) if article_date is None else c.model_copy(update={"time": f"{article_date.year}년", "frequency": "년"})
    last_month = re.fullmatch(r"지난\s*(?P<month>\d{1,2})월", v)
    if last_month:
        if article_date is None:
            return _hold(c)
        month = int(last_month["month"])
        year = article_date.year if month <= article_date.month else article_date.year - 1
        return c.model_copy(update={"time": f"{year}년 {month}월", "frequency": "월"})
    bare_month = re.fullmatch(r"(?P<month>\d{1,2})월", v)
    if bare_month:
        if article_date is None:
            return _hold(c)
        month = int(bare_month["month"])
        if not 1 <= month <= 12:
            return c
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


def _normalize_explicit_frequency(c):
    """Trust an exact period written in the time slot over a conflicting label."""
    value = re.sub(r"\s+", "", (c.time or ""))
    if not value:
        return c
    if (
        re.fullmatch(r"(?:19|20)\d{2}년?\d{1,2}월", value)
        or re.fullmatch(r"(?:19|20)\d{2}[-.]\d{1,2}", value)
    ):
        frequency = "월"
    elif re.fullmatch(r"(?:19|20)\d{2}년?[1-4]분기", value):
        frequency = "분기"
    elif re.fullmatch(r"(?:19|20)\d{2}년?(?:상|하)반기", value):
        frequency = "반기"
    else:
        return c
    if c.frequency == frequency:
        return c
    return c.model_copy(update={"frequency": frequency})


_BARE_MONTH = re.compile(
    r"(?<![\d~～∼\-–])(?P<month>1[0-2]|[1-9])월(?!\s*\d{1,2}일)"
)
_MONTH_QUALIFIER = re.compile(
    r"(?:(?:19|20)\d{2}년|작년|지난해|전년|올해|금년|지난)\s*$"
)


def _resolve_source_reporting_month(c, article_date: date | None):
    """Replace a stored annual slot only when the source binds one month to the indicator."""
    if article_date is None or not c.indicator:
        return c
    frequency = re.sub(r"\s+", "", (c.frequency or "")).casefold()
    if frequency not in {"y", "year", "yearly", "annual", "연", "연간", "년"}:
        return c
    if not re.fullmatch(r"(?:19|20)\d{2}년?", (c.time or "").strip()):
        return c

    indicator = r"\s*".join(re.escape(part) for part in c.indicator.split())
    pattern = re.compile(
        rf"(?<![\d~～∼\-–])"
        rf"(?:(?P<year>(?:19|20)\d{{2}})년|"
        rf"(?P<relative>올해|금년|지난해|작년|전년|지난)\s*)?"
        rf"(?P<month>1[0-2]|[1-9])월(?!\s*\d{{1,2}}일)"
        rf"[^.!?。！？]{{0,24}}?{indicator}"
    )
    resolved: set[tuple[int, int]] = set()
    for match in pattern.finditer(c.source_sentence):
        month = int(match["month"])
        explicit_year = match["year"]
        relative = match["relative"]
        if explicit_year:
            year = int(explicit_year)
        elif relative in {"지난해", "작년", "전년"}:
            year = article_date.year - 1
        elif relative in {"올해", "금년"}:
            year = article_date.year
        else:
            year = article_date.year if month <= article_date.month else article_date.year - 1
        resolved.add((year, month))
    if len(resolved) != 1:
        return c
    year, month = resolved.pop()
    return c.model_copy(update={"time": f"{year}년 {month}월", "frequency": "월"})


def _resolve_source_previous_month(c, article_date: date | None):
    """Recover only a unique bare month equal to the article's previous month."""
    if article_date is None:
        return c
    matches = list(_BARE_MONTH.finditer(c.source_sentence))
    if len(matches) != 1:
        return c
    if _MONTH_QUALIFIER.search(c.source_sentence[: matches[0].start()]):
        return c
    month = int(matches[0]["month"])
    previous_year = article_date.year if article_date.month > 1 else article_date.year - 1
    previous_month = article_date.month - 1 if article_date.month > 1 else 12
    if month != previous_month:
        return c
    return c.model_copy(update={"time": f"{previous_year}년 {month}월", "frequency": "월"})


def _hold(c):
    return c.model_copy(update={"parse_status": "HOLD", "parse_reason": "ARTICLE_DATE_REQUIRED_FOR_RELATIVE_TIME"})
