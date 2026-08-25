"""Deterministic guard for non-statistical numeric roles selected by an extractor."""

from __future__ import annotations

import re

from schemas.claim import ClaimSchema


_AGE_DECADES = {10, 20, 30, 40, 50, 60, 70, 80, 90}
_AGE_SUBJECTS = (
    "청년", "남성", "여성", "인구", "취업자", "실업자", "사망자",
    "근로자", "연령", "세대", "사람", "주민", "유권자",
)
_AGE_PARTICLES = r"(?:는|은|이|가|의|에서|중|에게|를|도|부터|까지)?"


def target_numeric_role_conflict(claim: ClaimSchema) -> str | None:
    """Return a stable reason when Claim value/unit only denotes context."""
    integer_value = _integer_value(claim.value)
    if integer_value is None or not claim.unit:
        return None
    compact_unit = re.sub(r"\s+", "", claim.unit)
    source = claim.source_sentence
    if compact_unit == "대" and _is_age_group_target(source, integer_value):
        return "TARGET_NUMERIC_ROLE_CONFLICT:AGE_GROUP"
    if compact_unit in {"개", "개월"} and _is_duration_target(source, integer_value):
        return "TARGET_NUMERIC_ROLE_CONFLICT:DURATION"
    return None


def _integer_value(value: float | None) -> int | None:
    if value is None:
        return None
    number = float(value)
    if not number.is_integer():
        return None
    return int(abs(number))


def _is_age_group_target(source: str, value: int) -> bool:
    if value not in _AGE_DECADES:
        return False
    pattern = re.compile(rf"(?<!\d){value}\s*대")
    matches = list(pattern.finditer(source))
    if not matches:
        return False
    protected = 0
    for match in matches:
        following = source[match.end():]
        preceding = source[max(0, match.start() - 16):match.start()]
        coordinated = re.match(
            r"\s*(?:와|과)\s*(?:10|20|30|40|50|60|70|80|90)\s*대",
            following,
        )
        subject = re.match(
            rf"\s*{_AGE_PARTICLES}\s*(?:{'|'.join(_AGE_SUBJECTS)})",
            following,
        )
        population_context = re.search(
            r"(?:인구|취업자|실업자|사망자|근로자|연령|세대)\s*(?:중|가운데)?\s*$",
            preceding,
        )
        if coordinated or subject or population_context:
            protected += 1
    return protected == len(matches)


def _is_duration_target(source: str, value: int) -> bool:
    duration = re.search(rf"(?<!\d){value}\s*개월(?:간)?", source)
    if duration is None:
        return False
    direct_count = re.search(rf"(?<!\d){value}\s*개(?!\s*월)", source)
    return direct_count is None
