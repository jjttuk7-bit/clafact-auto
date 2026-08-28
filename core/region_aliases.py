"""Source-grounded region aliases shared by coordinate stages."""

from __future__ import annotations


NATIONAL_REGION_ALIASES = frozenset({"전국", "대한민국", "한국", "국내"})


def normalize_national_region(value: str | None) -> str | None:
    """Normalize only an exact national alias; never rewrite compound concepts."""
    stripped = (value or "").strip()
    return "전국" if stripped in NATIONAL_REGION_ALIASES else (stripped or None)
