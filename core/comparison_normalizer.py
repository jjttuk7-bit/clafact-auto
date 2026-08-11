"""Canonical comparison slot normalization for deterministic calculation planning."""

from collections.abc import Mapping


def normalize_comparison(value: Mapping[str, str] | None) -> dict[str, str] | None:
    """Normalize known comparison period aliases to the canonical ``basis`` key."""
    if not value:
        return None
    result = dict(value)
    if not result.get("basis"):
        for alias in ("period", "reference_period"):
            if result.get(alias):
                result["basis"] = result[alias]
                break
    result.pop("period", None)
    result.pop("reference_period", None)
    return result
