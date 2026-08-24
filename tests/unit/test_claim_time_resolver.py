from datetime import date
from core.claim_time_resolver import resolve_relative_time
from schemas.claim import ClaimSchema

def claim(time,source=None):
 return ClaimSchema(claim_id='C',source_sentence=source or time,indicator='지표',value=1,unit='%',time=time,parse_status='AUTO_OK')

def test_last_month():
 r=resolve_relative_time(claim('지난달'),date(2025,11,4));assert (r.time,r.frequency)==('2025년 10월','월')
def test_relative_without_date_holds():
 r=resolve_relative_time(claim('지난달'),None);assert r.parse_status=='HOLD' and r.parse_reason=='ARTICLE_DATE_REQUIRED_FOR_RELATIVE_TIME'
def test_this_year_quarter():
 r=resolve_relative_time(claim('올해 1분기'),date(2024,4,30));assert (r.time,r.frequency)==('2024년 1분기','분기')
def test_last_year_quarter():
 r=resolve_relative_time(claim('지난해 4분기'),date(2025,2,1));assert (r.time,r.frequency)==('2024년 4분기','분기')
def test_half_year_is_supported_by_kosis_parameter_api():
 r=resolve_relative_time(claim('올해 상반기'),date(2024,8,1));assert (r.time,r.frequency,r.parse_status)==('2024년 상반기','반기','AUTO_OK')
def test_named_last_month():
 r=resolve_relative_time(claim('작년 11월'),date(2025,1,22));assert r.time=='2024년 11월'
def test_last_named_month():
 r=resolve_relative_time(claim('지난 8월'),date(2025,10,29));assert r.time=='2025년 8월'


def test_explicit_month_corrects_conflicting_annual_frequency() -> None:
    stored = claim("2025년 1월").model_copy(update={"frequency": "연"})

    result = resolve_relative_time(stored, date(2025, 2, 26))

    assert (result.time, result.frequency) == ("2025년 1월", "월")


def test_explicit_quarter_corrects_conflicting_monthly_frequency() -> None:
    stored = claim("2025년 1분기").model_copy(update={"frequency": "월"})

    result = resolve_relative_time(stored, date(2025, 4, 30))

    assert (result.time, result.frequency) == ("2025년 1분기", "분기")


def test_this_year_first_month_resolves_to_january() -> None:
    result = resolve_relative_time(claim("올해 첫 달"), date(2025, 2, 26))

    assert (result.time, result.frequency) == ("2025년 1월", "월")


def _missing_time(source: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="missing-month",
        source_sentence=source,
        indicator="소비자물가 상승률",
        value=2.2,
        unit="%",
        time=None,
        calculation="DIRECT_VALUE",
        parse_status="HOLD",
        parse_reason="MISSING_REQUIRED_SLOTS:time",
    )


def test_recovers_unique_bare_month_only_when_it_is_previous_article_month() -> None:
    result = resolve_relative_time(
        _missing_time("6월 소비자물가 상승률은 2.2%였다."),
        date(2025, 7, 2),
    )

    assert (result.time, result.frequency) == ("2025년 6월", "월")


def test_does_not_recover_month_that_is_part_of_calendar_day() -> None:
    result = resolve_relative_time(_missing_time("6월 25일 지수는 2.2%였다."), date(2025, 7, 2))
    assert result.time is None


def test_does_not_recover_month_range() -> None:
    result = resolve_relative_time(_missing_time("올 1~6월 지수는 2.2%였다."), date(2025, 7, 2))
    assert result.time is None


def test_does_not_recover_non_previous_month_or_missing_article_date() -> None:
    claim_value = _missing_time("4월 소비자물가 상승률은 2.2%였다.")
    assert resolve_relative_time(claim_value, date(2025, 7, 2)).time is None
    assert resolve_relative_time(claim_value, None).time is None


def test_does_not_treat_year_qualified_month_as_bare_month() -> None:
    explicit_year = _missing_time("2024년 6월 소비자물가 상승률은 2.2%였다.")
    relative_year = _missing_time("작년 6월 소비자물가 상승률은 2.2%였다.")

    assert resolve_relative_time(explicit_year, date(2025, 7, 2)).time is None
    assert resolve_relative_time(relative_year, date(2025, 7, 2)).time is None


def test_repairs_annual_slot_when_source_explicitly_names_reporting_month_and_indicator() -> None:
    stored = ClaimSchema(
        claim_id="birth-month",
        source_sentence="25일 통계청은 4월 출생아 수가 전년 같은 달보다 8.7% 증가했다고 밝혔다.",
        indicator="출생아 수",
        value=8.7,
        unit="%",
        time="2024",
        frequency="Y",
        comparison={"type": "YEAR_OVER_YEAR"},
        calculation="GROWTH_RATE",
        condition={"direction": "INCREASE"},
        parse_status="AUTO_OK",
    )

    result = resolve_relative_time(stored, date(2025, 6, 26))

    assert (result.time, result.frequency) == ("2025년 4월", "월")


def test_does_not_repair_annual_slot_from_cumulative_month_range() -> None:
    stored = ClaimSchema(
        claim_id="birth-cumulative",
        source_sentence="작년 1~11월 누적 출생아 수는 22만94명으로 3% 늘었다.",
        indicator="출생아 수",
        value=3.0,
        unit="%",
        time="2024",
        frequency="Y",
        comparison={"type": "YEAR_OVER_YEAR"},
        calculation="GROWTH_RATE",
        condition={"direction": "INCREASE"},
        parse_status="AUTO_OK",
    )

    result = resolve_relative_time(stored, date(2025, 1, 23))

    assert (result.time, result.frequency) == ("2024", "Y")
