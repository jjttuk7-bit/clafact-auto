from datetime import date

from core.claim_time_resolver import resolve_relative_time
from schemas.claim import ClaimSchema


def test_resolve_relative_time_converts_last_month_using_article_date() -> None:
    claim = ClaimSchema(
        claim_id="CPI-1",
        source_sentence="지난달 소비자물가는 2.4% 올랐다.",
        indicator="소비자 물가",
        value=2.4,
        unit="%",
        time="지난달",
        parse_status="AUTO_OK",
    )

    result = resolve_relative_time(claim, date(2025, 11, 4))

    assert result.time == "2025년 10월"
    assert result.frequency == "월"


def test_resolve_relative_time_keeps_unresolved_relative_time_without_article_date() -> None:
    claim = ClaimSchema(
        claim_id="CPI-1",
        source_sentence="지난달 소비자물가는 2.4% 올랐다.",
        indicator="소비자 물가",
        value=2.4,
        unit="%",
        time="지난달",
        parse_status="AUTO_OK",
    )

    result = resolve_relative_time(claim, None)

    assert result.time == "지난달"
    assert result.parse_status == "HOLD"
    assert result.parse_reason == "ARTICLE_DATE_REQUIRED_FOR_RELATIVE_TIME"


def test_resolve_relative_time_converts_this_year_quarter_using_article_date() -> None:
    claim = ClaimSchema(
        claim_id="EXPORT-Q1",
        source_sentence="올해 1분기 중고차 수출액은 지난해보다 31% 증가했다.",
        indicator="수출액",
        value=31,
        unit="%",
        time="올해 1분기",
        frequency="분기",
        parse_status="AUTO_OK",
    )

    result = resolve_relative_time(claim, date(2024, 4, 30))

    assert result.time == "2024년 1분기"
    assert result.frequency == "분기"


def test_resolve_relative_time_converts_last_year_quarter_using_article_date() -> None:
    claim = ClaimSchema(
        claim_id="EXPORT-Q4",
        source_sentence="지난해 4분기 수출액은 증가했다.",
        indicator="수출액",
        value=1,
        unit="%",
        time="지난해 4분기",
        frequency="분기",
        parse_status="AUTO_OK",
    )

    result = resolve_relative_time(claim, date(2025, 2, 1))

    assert result.time == "2024년 4분기"
    assert result.frequency == "분기"


def test_resolve_relative_time_holds_half_year_until_kosis_period_is_supported() -> None:
    claim = ClaimSchema(
        claim_id="EXPORT-H1",
        source_sentence="올해 상반기 수출액은 증가했다.",
        indicator="수출액",
        value=1,
        unit="%",
        time="올해 상반기",
        frequency="반기",
        parse_status="AUTO_OK",
    )

    result = resolve_relative_time(claim, date(2024, 8, 1))

    assert result.time == "2024년 상반기"
    assert result.frequency == "반기"
    assert result.parse_status == "HOLD"
    assert result.parse_reason == "KOSIS_HALF_YEAR_PERIOD_UNSUPPORTED"
