from core.trade_official_publication import extract_trade_official_value
from schemas.claim import ClaimSchema


def _claim(**updates) -> ClaimSchema:
    payload = {
        "claim_id": "trade",
        "source_sentence": "수출액은 100억달러였다.",
        "indicator": "수출액",
        "value": 10_000_000_000,
        "unit": "달러",
        "time": "2024",
        "frequency": "Y",
        "calculation": "DIRECT_VALUE",
        "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema.model_validate(payload)


def test_extracts_monthly_export_level_only_from_exact_period_clause() -> None:
    claim = _claim(
        source_sentence="작년 12월 수출은 633억달러였다.",
        value=63_300_000_000,
        time="2024-12",
        frequency="M",
    )
    text = "2024년 12월 상품수지 수출이 633.0억달러로 전년동월대비 6.6% 증가"
    assert extract_trade_official_value(claim, text) == 63_300_000_000


def test_extracts_cumulative_trade_deficit_as_claim_magnitude() -> None:
    claim = _claim(
        source_sentence="연간 누계 무역 수지는 10억5600만달러 적자다.",
        indicator="무역수지",
        value=1_056_000_000,
        time="2025-01-01/2025-02-20",
        frequency="CUMULATIVE_PERIOD",
        condition={"polarity": "DEFICIT"},
    )
    text = "2025년 2월 1일~20일 연간누계 무역수지 -1,056 백만달러"
    assert extract_trade_official_value(claim, text) == 1_056_000_000


def test_extracts_total_country_and_computes_share_without_scope_leakage() -> None:
    text = (
        "2024년 수출총액 6,836.9억달러. "
        "주요지역별 수출 미국 1,277.9억달러."
    )
    total = _claim(value=683_600_000_000, condition={"trade_claim_role": "TOTAL_EXPORT"})
    country = _claim(
        value=127_800_000_000,
        dimension={"raw": '{"교역상대국": ["미국"]}'},
        condition={"trade_claim_role": "COUNTRY_EXPORT"},
    )
    share = _claim(
        indicator="수출 비중",
        value=18.7,
        unit="%",
        calculation="SHARE",
        dimension={"raw": '{"교역상대국": ["미국"]}'},
        comparison={
            "type": "SHARE_OF_TOTAL",
            "numerator": "대미 수출액",
            "denominator": "우리나라 총수출액",
            "denominator_member": "전체",
        },
        condition={"trade_claim_role": "COUNTRY_SHARE"},
    )
    assert extract_trade_official_value(total, text) == 683_690_000_000
    assert extract_trade_official_value(country, text) == 127_790_000_000
    assert round(extract_trade_official_value(share, text) or 0, 3) == 18.691


def test_extracts_partial_period_us_decline_with_direction_guard() -> None:
    claim = _claim(
        source_sentence="지난 1~10일 대미 수출액은 전년 동기 대비 0.6% 감소했다.",
        value=0.6,
        unit="%",
        time="2025-04-01/2025-04-10",
        frequency="PARTIAL_PERIOD",
        dimension={"raw": '{"교역상대국": ["미국"]}'},
        comparison={"type": "YEAR_OVER_YEAR"},
        calculation="GROWTH_RATE",
        condition={"direction": "DECREASE"},
    )
    text = "4월 1일∼10일 주요국가 미국(△0.6%) 등 감소"
    assert extract_trade_official_value(claim, text) == 0.6
    assert extract_trade_official_value(
        claim.model_copy(update={"condition": {"direction": "INCREASE"}}), text
    ) is None


def test_fails_closed_when_two_different_official_values_match() -> None:
    claim = _claim(
        source_sentence="지난 1~10일 대미 수출액은 0.6% 감소했다.",
        value=0.6,
        unit="%",
        time="2025-04-01/2025-04-10",
        calculation="GROWTH_RATE",
        condition={"direction": "DECREASE"},
    )
    text = "미국(△0.6%) 감소, 미국(△0.7%) 감소"
    assert extract_trade_official_value(claim, text) is None
