"""Deterministic value extraction from period-specific official trade releases."""

from __future__ import annotations

import re

from schemas.claim import ClaimSchema


_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"


def extract_trade_official_value(claim: ClaimSchema, document_text: str) -> float | None:
    """Return one uniquely period-and-scope-grounded value; ambiguity returns None."""
    text = re.sub(r"\s+", "", document_text)
    role = str((claim.condition or {}).get("trade_claim_role") or "").upper()
    if role in {"TOTAL_EXPORT", "COUNTRY_EXPORT", "COUNTRY_SHARE"}:
        total, country = _annual_total_and_us(text)
        if role == "TOTAL_EXPORT":
            return total
        if role == "COUNTRY_EXPORT":
            return country
        if total is None or country is None or total == 0:
            return None
        return country / total * 100.0

    indicator = re.sub(r"\s+", "", claim.indicator or "")
    if "무역수지" in indicator:
        value = _cumulative_trade_balance(text)
        if value is None:
            return None
        polarity = str((claim.condition or {}).get("polarity") or "").upper()
        if polarity == "DEFICIT" and value >= 0:
            return None
        if polarity == "SURPLUS" and value < 0:
            return None
        return abs(value) * 1_000_000.0

    if claim.calculation == "GROWTH_RATE" and (claim.unit or "") in {"%", "％", "퍼센트"}:
        direction = str((claim.condition or {}).get("direction") or "").upper()
        if direction == "DECREASE":
            patterns = [
                rf"미국\((?:△|-)(?P<value>{_NUMBER})%\)[^。.!?]{{0,20}}감소",
                rf"미국[^。.!?]{{0,20}}(?P<value>{_NUMBER})%감소",
            ]
        elif direction == "INCREASE":
            patterns = [rf"미국[^。.!?]{{0,20}}(?P<value>{_NUMBER})%증가"]
        else:
            return None
        return _unique_from_patterns(text, patterns)

    if "수출" in indicator and (claim.unit or "") in {"달러", "USD", "억달러"}:
        period = str(claim.time or "")
        match = re.fullmatch(r"(?P<year>\d{4})-(?P<month>\d{2})", period)
        if match is None:
            return None
        anchor = f"{match.group('year')}년{int(match.group('month'))}월"
        segments = text.split(anchor)
        if len(segments) < 2:
            return None
        return _unique_scaled(
            "\n".join(segment[:800] for segment in segments[1:]),
            rf"상품수지[^。.!?]{{0,40}}수출(?:이|은)?(?P<value>{_NUMBER})억달러",
            100_000_000.0,
        )
    return None


def _annual_total_and_us(text: str) -> tuple[float | None, float | None]:
    total = _unique_scaled(text, rf"수출총액(?P<value>{_NUMBER})억달러", 100_000_000.0)
    country = _unique_scaled(text, rf"(?:주요지역별수출)?미국(?P<value>{_NUMBER})억달러", 100_000_000.0)
    if total is None:
        total = _last_amount_in_row(text, "수출총액", ("화공품", "철강제품"))
    if country is None:
        section = text.split("주요지역별수출", 1)[-1]
        country = _last_amount_in_row(section, "미국", ("일본",))
    return total, country


def _last_amount_in_row(text: str, start: str, end_markers: tuple[str, ...]) -> float | None:
    start_at = text.find(start)
    if start_at < 0:
        return None
    ends = [text.find(marker, start_at + len(start)) for marker in end_markers]
    ends = [item for item in ends if item >= 0]
    if not ends:
        return None
    row = text[start_at + len(start):min(ends)]
    amounts = re.findall(rf"(?P<amount>{_NUMBER})\([△+-]?{_NUMBER}\)", row)
    if not amounts:
        return None
    return float(round(float(amounts[-1].replace(",", "")) * 100_000_000.0))


def _cumulative_trade_balance(text: str) -> float | None:
    explicit = re.findall(rf"연간누계무역수지(?P<value>[-△]?{_NUMBER})백만달러", text)
    if len(set(explicit)) == 1:
        return _signed_number(explicit[0])
    start = text.find("무역수지")
    end = text.find("※조업일수", start)
    if start < 0 or end < 0:
        return None
    values = re.findall(rf"[-△]?{_NUMBER}", text[start + len("무역수지"):end])
    return _signed_number(values[-1]) if values else None


def _signed_number(value: str) -> float:
    normalized = value.replace(",", "").replace("△", "-")
    return float(normalized)


def _unique_scaled(text: str, pattern: str, scale: float) -> float | None:
    values = {
        float(round(float(match.group("value").replace(",", "")) * scale))
        for match in re.finditer(pattern, text)
    }
    return next(iter(values)) if len(values) == 1 else None


def _unique_from_patterns(text: str, patterns: list[str]) -> float | None:
    values: set[float] = set()
    for pattern in patterns:
        values.update(
            float(match.group("value").replace(",", ""))
            for match in re.finditer(pattern, text)
        )
    return next(iter(values)) if len(values) == 1 else None
