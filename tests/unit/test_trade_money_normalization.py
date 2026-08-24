from datetime import date
from types import SimpleNamespace

import pytest

from core.trade_claim_recovery import recover_trade_period
from core.unified_claim_pipeline import verify_article
from schemas.claim import ClaimSchema


def _claim(*, value: float, unit: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="scaled-cumulative-balance",
        source_sentence="연간 누계 무역 수지는 10억5600만달러 적자다.",
        indicator="무역 수지",
        value=value,
        unit=unit,
        time="연간 누계",
        frequency="YTD",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        (-1.056, "십억 달러"),
        (-10.56, "억 달러"),
        (-1_056_000_000, "달러"),
    ],
)
def test_normalizes_equivalent_dollar_scales_from_source(
    value: float, unit: str,
) -> None:
    recovered = recover_trade_period(_claim(value=value, unit=unit), date(2025, 2, 21))

    assert recovered.value == -1_056_000_000
    assert recovered.unit == "달러"
    assert recovered.time == "2025-01-01/2025-02-20"
    assert recovered.frequency == "CUMULATIVE_PERIOD"
    assert recovered.condition == {"polarity": "DEFICIT"}


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        (-1.057, "십억 달러"),
        (-1.056, "십억 원"),
    ],
)
def test_does_not_normalize_money_when_amount_or_currency_disagrees(
    value: float, unit: str,
) -> None:
    recovered = recover_trade_period(_claim(value=value, unit=unit), date(2025, 2, 21))

    assert recovered.value == value
    assert recovered.unit == unit


class _ScaledUnitExtractor:
    def extract(self, source_sentence: str, **kwargs) -> ClaimSchema:
        return _claim(value=-1.056, unit="십억 달러")


class _OfficialService:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim: ClaimSchema, *, article_date: date):
        self.claims.append(claim)
        return SimpleNamespace(
            verdict=SimpleNamespace(route_status="AUTO", reason_code=None)
        )


def test_dashboard_boundary_sends_normalized_money_to_official_service() -> None:
    service = _OfficialService()

    result = verify_article(
        "연간 누계 무역 수지는 10억5600만달러 적자다.",
        article_published_at=date(2025, 2, 21),
        extractor=_ScaledUnitExtractor(),
        official_service=service,
    )

    assert result.entries[0].claim.value == -1_056_000_000
    assert result.entries[0].claim.unit == "달러"
    assert result.entries[0].claim.time == "2025-01-01/2025-02-20"
    assert result.entries[0].claim.frequency == "CUMULATIVE_PERIOD"
    assert result.entries[0].claim.parse_status == "AUTO_OK"
    assert len(service.claims) == 1
