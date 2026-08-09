"""As-of safeguards for historical fact-checking evidence."""

from __future__ import annotations

from datetime import date
from typing import Any


def filter_rows_as_of(rows: list[dict[str, Any]], article_date: date) -> list[dict[str, Any]]:
    """Keep dated official rows or explicitly adjudicated Goldset historical snapshots."""
    accepted: list[dict[str, Any]] = []
    for row in rows:
        if row.get("as_of_verified_by_goldset") is True:
            accepted.append(row)
            continue
        raw_date = row.get("LST_CHN_DE") or row.get("last_changed_at")
        if not isinstance(raw_date, str):
            continue
        try:
            published = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if published <= article_date:
            accepted.append(row)
    return accepted
