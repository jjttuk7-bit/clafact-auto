"""Deterministic measurement-unit scale conversions."""

_SCALE = {"명": 1.0, "천명": 1_000.0, "가구": 1.0, "천가구": 1_000.0, "달러": 1.0, "천달러": 1_000.0}
_ALIASES = {
    "person": "명", "persons": "명", "thousand persons": "천명",
    "천불": "천달러", "천$": "천달러", "usd": "달러", "1,000 usd": "천달러", "thousand dollars": "천달러",
}


def _normalized(unit: str) -> str:
    return _ALIASES.get(unit.strip().casefold(), unit)


def compatible_units(left: str, right: str) -> bool:
    left, right = _normalized(left), _normalized(right)
    return left == right or (left in _SCALE and right in _SCALE and left.replace("천", "") == right.replace("천", ""))


def convert_value(value: float, source_unit: str, target_unit: str) -> float:
    source_unit, target_unit = _normalized(source_unit), _normalized(target_unit)
    if not compatible_units(source_unit, target_unit):
        raise ValueError("incompatible units")
    return value * _SCALE.get(source_unit, 1.0) / _SCALE.get(target_unit, 1.0)
