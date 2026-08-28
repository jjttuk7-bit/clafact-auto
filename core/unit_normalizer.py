"""Deterministic measurement-unit scale conversions."""

import re


_SCALE = {
    "명": 1.0,
    "천명": 1_000.0,
    "만명": 10_000.0,
    "가구": 1.0,
    "천가구": 1_000.0,
    "만가구": 10_000.0,
    "원": 1.0,
    "천원": 1_000.0,
    "만원": 10_000.0,
    "백만원": 1_000_000.0,
    "억원": 100_000_000.0,
    "십억원": 1_000_000_000.0,
    "조원": 1_000_000_000_000.0,
    "달러": 1.0,
    "천달러": 1_000.0,
    "만달러": 10_000.0,
    "억달러": 100_000_000.0,
    "십억달러": 1_000_000_000.0,
    "개": 1.0,
    "곳": 1.0,
}
_FAMILY = {
    "명": "PERSON", "천명": "PERSON", "만명": "PERSON",
    "가구": "HOUSEHOLD", "천가구": "HOUSEHOLD", "만가구": "HOUSEHOLD",
    "원": "KRW", "천원": "KRW", "만원": "KRW", "백만원": "KRW",
    "억원": "KRW", "십억원": "KRW", "조원": "KRW",
    "달러": "USD", "천달러": "USD", "만달러": "USD", "억달러": "USD",
    "십억달러": "USD",
    "개": "COUNT", "곳": "COUNT",
}
_ALIASES = {
    "person": "명",
    "persons": "명",
    "thousand persons": "천명",
    "천불": "천달러",
    "천$": "천달러",
    "천 달러": "천달러",
    "usd": "달러",
    "1,000 usd": "천달러",
    "thousand dollars": "천달러",
    "ha": "헥타르",
    "㏊": "헥타르",
}


def _normalized(unit: str) -> str:
    raw = unit.strip().casefold()
    if match := re.search(r"(?P<year>\d{4})\s*년?\s*=\s*100", raw):
        return f"index:{match.group('year')}=100"
    compact = re.sub(r"\s+", "", raw)
    return _ALIASES.get(raw, _ALIASES.get(compact, compact))


def compatible_units(left: str, right: str) -> bool:
    left, right = _normalized(left), _normalized(right)
    return left == right or (
        left in _SCALE and right in _SCALE and _FAMILY[left] == _FAMILY[right]
    )


def convert_value(value: float, source_unit: str, target_unit: str) -> float:
    source_unit, target_unit = _normalized(source_unit), _normalized(target_unit)
    if not compatible_units(source_unit, target_unit):
        raise ValueError("incompatible units")
    return value * _SCALE.get(source_unit, 1.0) / _SCALE.get(target_unit, 1.0)
