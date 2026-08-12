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
