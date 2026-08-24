"""Source-grounded period and numeric-scope recovery for trade Claims."""

from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import re

from core.trade_money_normalizer import normalize_trade_money
from schemas.claim import ClaimSchema


_PARTIAL_PERIOD = re.compile(
    r"(?:(?P<month>1[0-2]|[1-9])\s*월\s*)?"
    r"(?P<start>\d{1,2})\s*[~～∼\-–]\s*"
    r"(?:(?P<end_month>1[0-2]|[1-9])\s*월\s*)?"
    r"(?P<end>\d{1,2})\s*일"
)
_MONEY = r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?(?:조|억|만|천)?달러"
_TOTAL_COUNTRY_SHARE = re.compile(
    rf"(?:우리나라|한국|전체)?\s*수출(?:액)?\s*(?P<total>{_MONEY})"
    rf"(?:\s*\([^)]*원\))?\s*중\s*"
    rf"(?P<scope>대미(?:\s*\(對美\))?|미국(?:향|으로의)?)\s*수출(?:액)?은\s*"
    rf"(?P<country>{_MONEY})로\s*(?P<share>\d+(?:\.\d+)?)\s*%"
)
_SCALES = {"조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3}


def recover_trade_period(claim: ClaimSchema, article_date: date | None) -> ClaimSchema:
    """Recover exact trade publication ranges only from explicit source signals."""
    if not _is_trade_claim(claim):
        return claim
    claim = normalize_trade_money(claim)
    source = claim.source_sentence
    partial = _PARTIAL_PERIOD.search(source)
    if partial is not None and article_date is not None:
        month = int(partial.group("month") or article_date.month)
        end_month = int(partial.group("end_month") or month)
        year = article_date.year
        if month > article_date.month:
            year -= 1
        try:
            start = date(year, month, int(partial.group("start")))
            end_year = year + int(end_month < month)
            end = date(end_year, end_month, int(partial.group("end")))
        except ValueError:
            return claim.model_copy(update={
                "parse_status": "HOLD",
                "parse_reason": "TRADE_PERIOD_RANGE_INVALID",
            })
        if end < start:
            return claim.model_copy(update={
                "parse_status": "HOLD",
                "parse_reason": "TRADE_PERIOD_RANGE_INVALID",
            })
        return claim.model_copy(update={
            "time": f"{start.isoformat()}/{end.isoformat()}",
            "frequency": "PARTIAL_PERIOD",
        })
    if "연간 누계" in source and "무역수지" in source.replace(" ", ""):
        if article_date is None:
            return claim.model_copy(update={
                "parse_status": "HOLD",
                "parse_reason": "ARTICLE_DATE_REQUIRED_FOR_CUMULATIVE_PERIOD",
            })
        year = _claim_year(claim.time) or article_date.year
        if year != article_date.year:
            return claim.model_copy(update={
                "parse_status": "HOLD",
                "parse_reason": "CUMULATIVE_PERIOD_YEAR_CONFLICT",
            })
        end = article_date - timedelta(days=1)
        condition = dict(claim.condition or {})
        if "적자" in source:
            condition["polarity"] = "DEFICIT"
        elif "흑자" in source:
            condition["polarity"] = "SURPLUS"
        return claim.model_copy(update={
            "time": f"{year:04d}-01-01/{end.isoformat()}",
            "frequency": "CUMULATIVE_PERIOD",
            "condition": condition or claim.condition,
        })
    return claim


def split_trade_composite_claim(
    claim: ClaimSchema, article_date: date | None
) -> list[ClaimSchema]:
    """Split total, country amount, and country share without leaking dimensions."""
    if not _is_trade_claim(claim):
        return [claim]
    match = _TOTAL_COUNTRY_SHARE.search(claim.source_sentence)
    if match is None:
        return [claim]
    total = _money_value(match.group("total"))
    country = _money_value(match.group("country"))
    share = float(match.group("share"))
    if total is None or country is None or total <= 0 or country <= 0:
        return [claim]
    dimension = claim.dimension or {"raw": '{"교역상대국": ["미국"]}'}
    base_updates = {
        "source_sentence": claim.source_sentence,
        "indicator": "수출액",
        "time": claim.time,
        "frequency": claim.frequency,
        "region": claim.region,
        "population": claim.population,
        "source_hint": claim.source_hint,
        "parse_status": "AUTO_OK",
        "parse_reason": None,
    }
    total_claim = claim.model_copy(update={
        **base_updates,
        "claim_id": _child_id(claim.source_sentence, "TOTAL_EXPORT"),
        "value": total,
        "unit": "달러",
        "dimension": None,
        "comparison": None,
        "calculation": "DIRECT_VALUE",
        "condition": {"trade_claim_role": "TOTAL_EXPORT"},
    })
    country_claim = claim.model_copy(update={
        **base_updates,
        "claim_id": _child_id(claim.source_sentence, "COUNTRY_EXPORT"),
        "value": country,
        "unit": "달러",
        "dimension": dimension,
        "comparison": None,
        "calculation": "DIRECT_VALUE",
        "condition": {"trade_claim_role": "COUNTRY_EXPORT"},
    })
    share_claim = claim.model_copy(update={
        **base_updates,
        "claim_id": _child_id(claim.source_sentence, "COUNTRY_SHARE"),
        "indicator": "수출 비중",
        "value": share,
        "unit": "%",
        "dimension": dimension,
        "comparison": {
            "type": "SHARE_OF_TOTAL",
            "numerator": "대미 수출액",
            "denominator": "우리나라 총수출액",
            "denominator_member": "전체",
        },
        "calculation": "SHARE",
        "condition": {"trade_claim_role": "COUNTRY_SHARE"},
    })
    return [
        recover_trade_period(item, article_date)
        for item in (total_claim, country_claim, share_claim)
    ]


def _is_trade_claim(claim: ClaimSchema) -> bool:
    text = re.sub(r"\s+", "", f"{claim.indicator or ''} {claim.source_sentence}")
    return any(term in text for term in ("수출", "수입", "무역수지"))


def _claim_year(value: str | None) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", str(value or ""))
    return int(match.group()) if match else None


def _money_value(expression: str) -> float | None:
    compact = expression.replace(",", "").replace("달러", "")
    match = re.fullmatch(r"(?P<number>[+-]?\d+(?:\.\d+)?)(?P<scale>조|억|만|천)?", compact)
    if match is None:
        return None
    return float(match.group("number")) * _SCALES.get(match.group("scale") or "", 1.0)


def _child_id(source_sentence: str, role: str) -> str:
    digest = sha256(f"{source_sentence}\n{role}".encode("utf-8")).hexdigest()[:16]
    return f"claim_{digest}"
