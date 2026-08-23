"""Period expansion for record-comparison evidence coordinates."""

from __future__ import annotations

import re


_ANNUAL = {"Y", "YEAR", "YEARLY", "ANNUAL", "\ub144", "\uc5f0"}
_MONTHLY = {"M", "MONTH", "MONTHLY", "\uc6d4"}
_QUARTERLY = {"Q", "QUARTER", "QUARTERLY", "\ubd84\uae30"}


def enumerate_record_periods(
    start_period: str | None,
    current_period: str,
    frequency: str,
    *,
    max_periods: int = 1200,
) -> list[str] | None:
    """Return every comparable period without truncating unsafe ranges."""
    if not start_period or max_periods < 1:
        return None
    normalized_frequency = frequency.replace(" ", "").upper()
    if normalized_frequency in _ANNUAL:
        return _annual(start_period, current_period, max_periods)
    if normalized_frequency in _MONTHLY:
        return _monthly(start_period, current_period, max_periods)
    if normalized_frequency in _QUARTERLY:
        return _quarterly(start_period, current_period, max_periods)
    return None



def is_period_within_official_range(
    start_period: str | None,
    current_period: str,
    end_period: str | None,
    frequency: str,
) -> bool:
    """Return whether the current coordinate is inside one official range."""
    if not start_period or not end_period:
        return False
    normalized_frequency = frequency.replace(" ", "").upper()
    if normalized_frequency in _ANNUAL:
        def parser(value: str) -> int | None:
            return int(value) if re.fullmatch(r"\d{4}", value) else None
    elif normalized_frequency in _MONTHLY:
        def parser(value: str) -> int | None:
            return _year_part(value, 12)
    elif normalized_frequency in _QUARTERLY:
        def parser(value: str) -> int | None:
            return _year_part(value, 4, quarter=True)
    else:
        return False
    first = parser(start_period)
    current = parser(current_period)
    last = parser(end_period)
    if first is None or current is None or last is None:
        return False
    return first <= current <= last

def enumerate_same_month_periods(
    start_period: str | None,
    current_period: str,
    *,
    max_periods: int = 1200,
) -> list[str] | None:
    """Return the Claim month once per year for a month-basis record assertion."""
    if not start_period or max_periods < 1:
        return None
    start = re.fullmatch(r"(?P<year>\d{4})[.-]?(?P<month>0[1-9]|1[0-2])", start_period)
    current = re.fullmatch(r"(?P<year>\d{4})(?P<separator>[.-]?)(?P<month>0[1-9]|1[0-2])", current_period)
    if start is None or current is None:
        return None
    target_month = int(current["month"])
    first = int(start["year"]) + int(target_month < int(start["month"]))
    last = int(current["year"])
    if first > last or last - first + 1 > max_periods:
        return None
    separator = current["separator"]
    month = f"{target_month:02d}"
    return [f"{year:04d}{separator}{month}" for year in range(first, last + 1)]


def _annual(start: str, current: str, limit: int) -> list[str] | None:
    if not re.fullmatch(r"\d{4}", start) or not re.fullmatch(r"\d{4}", current):
        return None
    first, last = int(start), int(current)
    return _bounded(range(first, last + 1), limit, lambda value: f"{value:04d}")


def _monthly(start: str, current: str, limit: int) -> list[str] | None:
    first = _year_part(start, 12)
    last = _year_part(current, 12)
    if first is None or last is None:
        return None
    separator = "." if "." in current else "-" if "-" in current else ""
    return _bounded(
        range(first, last + 1),
        limit,
        lambda value: f"{value // 12:04d}{separator}{value % 12 + 1:02d}",
    )


def _quarterly(start: str, current: str, limit: int) -> list[str] | None:
    first = _year_part(start, 4, quarter=True)
    last = _year_part(current, 4, quarter=True)
    if first is None or last is None:
        return None
    separator = "-" if "-" in current else "." if "." in current else ""
    return _bounded(
        range(first, last + 1),
        limit,
        lambda value: f"{value // 4:04d}{separator}Q{value % 4 + 1}",
    )


def _year_part(raw: str, periods_per_year: int, *, quarter: bool = False) -> int | None:
    if quarter:
        pattern = r"(?P<year>\d{4})(?:[.-]?Q(?P<part>[1-4])|\s+(?P<fraction_part>[1-4])/4)"
        match = re.fullmatch(pattern, raw, re.IGNORECASE)
        part = match["part"] or match["fraction_part"] if match else None
    else:
        pattern = r"(?P<year>\d{4})[.-]?(?P<part>0[1-9]|1[0-2])"
        match = re.fullmatch(pattern, raw, re.IGNORECASE)
        part = match["part"] if match else None
    if match is None:
        return None
    return int(match["year"]) * periods_per_year + int(part) - 1


def _bounded(values: range, limit: int, formatter) -> list[str] | None:
    if values.stop <= values.start or len(values) > limit:
        return None
    return [formatter(value) for value in values]
