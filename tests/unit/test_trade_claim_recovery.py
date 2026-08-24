from datetime import date
from importlib import import_module

from schemas.claim import ClaimSchema


def _trade_module():
    return import_module("core.trade_claim_recovery")


def test_recovers_exact_first_ten_day_period_instead_of_annual_period() -> None:
    claim = ClaimSchema(
        claim_id="partial-us-export",
        source_sentence=(
            "지난 1~10일 대미 수출액은 34억7300만달러로 "
            "전년 동기 대비 0.6% 감소했다."
        ),
        indicator="수출액",
        value=0.6,
        unit="%",
        time="2025",
        frequency="Y",
        dimension={"raw": '{"교역상대국": ["미국"]}'},
        comparison={"type": "YEAR_OVER_YEAR"},
        calculation="GROWTH_RATE",
        condition={"direction": "DECREASE"},
        parse_status="AUTO_OK",
    )

    recovered = _trade_module().recover_trade_period(claim, date(2025, 4, 12))

    assert recovered.time == "2025-04-01/2025-04-10"
    assert recovered.frequency == "PARTIAL_PERIOD"


def test_recovers_annual_cumulative_end_and_deficit_polarity() -> None:
    claim = ClaimSchema(
        claim_id="cumulative-balance",
        source_sentence="연간 누계 무역 수지는 10억5600만달러 적자다.",
        indicator="무역수지",
        value=1_056_000_000,
        unit="달러",
        time="2025",
        frequency="Y",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    recovered = _trade_module().recover_trade_period(claim, date(2025, 2, 21))

    assert recovered.time == "2025-01-01/2025-02-20"
    assert recovered.frequency == "CUMULATIVE_PERIOD"
    assert recovered.condition == {"polarity": "DEFICIT"}


def test_splits_total_country_amount_and_share_without_scope_leakage() -> None:
    claim = ClaimSchema(
        claim_id="mixed-export",
        source_sentence=(
            "지난해 우리나라 수출 6836억달러(약 1007조원) 중 "
            "대미(對美) 수출은 1278억달러로 18.7%에 달했다."
        ),
        indicator="수출액",
        value=683_600_000_000,
        unit="달러",
        time="2024",
        frequency="Y",
        region="전국",
        dimension={"raw": '{"교역상대국": ["미국"]}'},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    children = _trade_module().split_trade_composite_claim(claim, date(2025, 4, 1))

    assert [(child.value, child.unit, child.calculation) for child in children] == [
        (683_600_000_000, "달러", "DIRECT_VALUE"),
        (127_800_000_000, "달러", "DIRECT_VALUE"),
        (18.7, "%", "SHARE"),
    ]
    assert children[0].dimension is None
    assert children[1].dimension == {"raw": '{"교역상대국": ["미국"]}'}
    assert children[2].dimension == {"raw": '{"교역상대국": ["미국"]}'}
    assert children[2].comparison == {
        "type": "SHARE_OF_TOTAL",
        "numerator": "대미 수출액",
        "denominator": "우리나라 총수출액",
        "denominator_member": "전체",
    }
    assert len({child.claim_id for child in children}) == 3


def test_does_not_split_unrelated_single_export_value() -> None:
    claim = ClaimSchema(
        claim_id="single",
        source_sentence="2024년 자동차 수출액은 100억달러였다.",
        indicator="수출액",
        value=10_000_000_000,
        unit="달러",
        time="2024",
        frequency="Y",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    assert _trade_module().split_trade_composite_claim(claim, date(2025, 1, 1)) == [claim]
