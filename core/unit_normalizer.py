"""Deterministic measurement-unit scale conversions."""
_SCALE = {"명": 1.0, "천명": 1_000.0, "가구": 1.0, "천가구": 1_000.0}
def compatible_units(left: str, right: str) -> bool:
    return left == right or (left in _SCALE and right in _SCALE and left.replace("천", "") == right.replace("천", ""))
def convert_value(value: float, source_unit: str, target_unit: str) -> float:
    if not compatible_units(source_unit, target_unit): raise ValueError("incompatible units")
    return value * _SCALE.get(source_unit, 1.0) / _SCALE.get(target_unit, 1.0)
