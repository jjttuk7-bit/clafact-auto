from core.deterministic_slot_enricher import infer_explicit_slots


def test_infers_year_over_year_growth_from_explicit_phrase() -> None:
    result = infer_explicit_slots("2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.")

    assert result.comparison == {"type": "YEAR_OVER_YEAR"}
    assert result.calculation == "GROWTH_RATE"
    assert result.condition is None


def test_infers_month_over_month_growth_from_explicit_phrase() -> None:
    result = infer_explicit_slots("지난달 대비 수출액은 2.1% 증가했다.")

    assert result.comparison == {"type": "MONTH_OVER_MONTH"}
    assert result.calculation == "GROWTH_RATE"


def test_infers_share_from_explicit_percentage_share_phrase() -> None:
    result = infer_explicit_slots("전체 수출에서 반도체 비중은 20%였다.")

    assert result.comparison == {"type": "SHARE_OF_TOTAL"}
    assert result.calculation == "SHARE"


def test_infers_direct_value_only_when_no_comparative_signal_exists() -> None:
    result = infer_explicit_slots("2024년 출생아 수는 24만2334명이었다.")

    assert result.comparison is None
    assert result.calculation == "DIRECT_VALUE"


def test_infers_explicit_condition() -> None:
    result = infer_explicit_slots("계절조정 실업률은 전월 대비 0.1%포인트 상승했다.")

    assert result.comparison == {"type": "MONTH_OVER_MONTH"}
    assert result.calculation == "GROWTH_RATE"
    assert result.condition == {"seasonal_adjustment": "계절조정"}


def test_leaves_ambiguous_direction_without_comparator_unenriched() -> None:
    result = infer_explicit_slots("수출은 3% 감소했다.")

    assert result.comparison is None
    assert result.calculation is None
    assert result.condition is None
