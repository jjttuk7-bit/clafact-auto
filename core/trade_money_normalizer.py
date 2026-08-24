"""Source-grounded base-unit normalization for trade money Claims."""

from __future__ import annotations

import math
import re

from schemas.claim import ClaimSchema


_SOURCE_DOLLAR_AMOUNT = re.compile(
    r"(?P<amount>[+-]?\d+(?:[,.]\d+)*"
    r"(?:(?:조|억|만|천)\d*(?:[,.]\d+)*)*)\s*달러"
)
_SCALES = {"조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3}
_UNIT_SCALES = (
    ("십억", 1e9),
    ("조", 1e12),
    ("억", 1e8),
    ("만", 1e4),
    ("천", 1e3),
)


def normalize_trade_money(claim: ClaimSchema) -> ClaimSchema:
    """Convert an equivalent dollar-scale output to source-backed base dollars."""
    if claim.value is None or not claim.unit:
        return claim
    claim_scale = _dollar_unit_scale(claim.unit)
    if claim_scale is None:
        return claim
    claim_amount = abs(float(claim.value)) * claim_scale
    source_amounts = _source_dollar_amounts(claim.source_sentence)
    if len(source_amounts) != 1:
        return claim

    source_expression, normalized_value = source_amounts[0]
    amounts_match = _amounts_equal(normalized_value, claim_amount)
    if not amounts_match and (
        claim.calculation != "DIRECT_VALUE"
        or not _is_power_of_ten_scale_mismatch(claim_amount, normalized_value)
    ):
        return claim
    if amounts_match and _claim_matches_source_expression(claim, source_expression):
        return claim
    condition = dict(claim.condition or {})
    compact_source = re.sub(r"\s+", "", claim.source_sentence)
    if "적자" in compact_source:
        normalized_value = -abs(normalized_value)
        condition["polarity"] = "DEFICIT"
    elif "흑자" in compact_source:
        normalized_value = abs(normalized_value)
        condition["polarity"] = "SURPLUS"
    elif float(claim.value) < 0:
        normalized_value = -abs(normalized_value)

    return claim.model_copy(update={
        "value": normalized_value,
        "unit": "달러",
        "condition": condition or claim.condition,
    })


def _dollar_unit_scale(unit: str) -> float | None:
    compact = re.sub(r"\s+", "", unit).casefold()
    if compact in {"달러", "usd", "미달러"}:
        return 1.0
    for prefix, scale in _UNIT_SCALES:
        if compact in {f"{prefix}달러", f"{prefix}usd", f"{prefix}미달러"}:
            return scale
    return None


def _source_dollar_amounts(source_sentence: str) -> list[tuple[str, float]]:
    return [
        (
            match.group("amount"),
            _parse_scaled_number(match.group("amount")),
        )
        for match in _SOURCE_DOLLAR_AMOUNT.finditer(source_sentence)
    ]


def _parse_scaled_number(raw: str) -> float:
    compact = raw.replace(",", "")
    if not any(scale in compact for scale in _SCALES):
        return abs(float(compact))
    total = 0.0
    remainder = compact.lstrip("+-")
    for marker, scale in (("조", 1e12), ("억", 1e8), ("만", 1e4), ("천", 1e3)):
        if marker not in remainder:
            continue
        group, remainder = remainder.split(marker, 1)
        total += (float(group) if group else 1.0) * scale
    total += float(remainder) if remainder else 0.0
    return total


def _amounts_equal(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= max(1e-6, abs(expected) * 1e-9)


def _is_power_of_ten_scale_mismatch(first: float, second: float) -> bool:
    """Return true only for an unambiguous 10x-or-larger scale error."""
    smaller = min(abs(first), abs(second))
    larger = max(abs(first), abs(second))
    if smaller == 0 or larger == 0:
        return False
    ratio = larger / smaller
    exponent = round(math.log10(ratio))
    return 1 <= exponent <= 12 and math.isclose(ratio, 10 ** exponent, rel_tol=1e-9)


def _claim_matches_source_expression(
    claim: ClaimSchema, source_expression: str,
) -> bool:
    compact_expression = source_expression.replace(",", "")
    direct = re.fullmatch(
        r"(?P<number>[+-]?\d+(?:\.\d+)?)(?P<scale>조|억|만|천)?",
        compact_expression,
    )
    if direct is None:
        return False
    compact_unit = re.sub(r"\s+", "", claim.unit or "").casefold()
    source_unit = f"{direct.group('scale') or ''}달러"
    return compact_unit == source_unit and _amounts_equal(
        abs(float(claim.value or 0)), abs(float(direct.group("number")))
    )
