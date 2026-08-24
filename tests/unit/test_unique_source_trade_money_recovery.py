from datetime import date

from core.trade_claim_recovery import recover_trade_period
from schemas.claim import ClaimSchema


def _claim(
    *,
    value: float,
    source_sentence: str = "연간 누계 무역 수지는 10억5600만달러 적자다.",
    calculation: str = "DIRECT_VALUE",
) -> ClaimSchema:
    return ClaimSchema(
        claim_id="unique-source-money",
        source_sentence=source_sentence,
        indicator="무역 수지",
        value=value,
        unit="십억 달러",
        time="연간 누계",
        frequency="YTD",
        calculation=calculation,
        parse_status="AUTO_OK",
    )


def test_recovers_power_of_ten_misscale_from_unique_source_amount() -> None:
    recovered = recover_trade_period(_claim(value=10.56), date(2025, 2, 21))

    assert recovered.value == -1_056_000_000
    assert recovered.unit == "달러"
    assert recovered.time == "2025-01-01/2025-02-20"
    assert recovered.parse_status == "AUTO_OK"


def test_does_not_override_when_source_has_multiple_dollar_amounts() -> None:
    recovered = recover_trade_period(
        _claim(
            value=10.56,
            source_sentence="수출은 100억달러, 수입은 90억달러였다.",
        ),
        date(2025, 2, 21),
    )

    assert recovered.value == 10.56
    assert recovered.unit == "십억 달러"


def test_does_not_override_calculated_claim() -> None:
    recovered = recover_trade_period(
        _claim(value=10.56, calculation="DIFFERENCE"),
        date(2025, 2, 21),
    )

    assert recovered.value == 10.56
    assert recovered.unit == "십억 달러"
