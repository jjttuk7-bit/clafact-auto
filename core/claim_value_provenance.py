"""Conservative source-text checks for numerical Claim values."""

from __future__ import annotations

import re


_PERCENT_VALUE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%(?!대)")


def has_explicit_percent_value(source_sentence: str, value: float) -> bool:
    """Return true only when the exact percentage, not a broad ``N%대`` band, is stated."""
    return any(abs(float(token) - value) < 1e-9 for token in _PERCENT_VALUE.findall(source_sentence))
