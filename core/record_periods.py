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
    pattern = r"(?P<year>\d{4})[.-]?Q(?P<part>[1-4])" if quarter else r"(?P<year>\d{4})[.-]?(?P<part>0[1-9]|1[0-2])"
    match = re.fullmatch(pattern, raw, re.IGNORECASE)
    if match is None:
        return None
    return int(match["year"]) * periods_per_year + int(match["part"]) - 1


def _bounded(values: range, limit: int, formatter) -> list[str] | None:
    if values.stop <= values.start or len(values) > limit:
        return None
    return [formatter(value) for value in values]
