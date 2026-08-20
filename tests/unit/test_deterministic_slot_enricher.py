from core.deterministic_slot_enricher import apply_explicit_slots, infer_explicit_slots
from schemas.claim import ClaimSchema
import pytest


def test_infers_year_over_year_growth_from_explicit_phrase() -> None:
    result = infer_explicit_slots("2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.")

    assert result.comparison == {"type": "YEAR_OVER_YEAR"}
    assert result.calculation == "GROWTH_RATE"
    assert result.condition is None


@pytest.mark.parametrize(
    "phrase",
    [
        "전년 같은 기간보다",
        "지난해 같은 기간 대비",
        "전년 동월보다",
        "작년 같은 달보다",
        "작년 3월에 비해",
        "1년 새",
    ],
)
def test_infers_year_over_year_from_equivalent_explicit_phrases(phrase: str) -> None:
    result = infer_explicit_slots(f"수출액은 {phrase} 3.8% 늘어났다.")

    assert result.comparison == {"type": "YEAR_OVER_YEAR"}


def test_infers_month_over_month_growth_from_explicit_phrase() -> None:
    result = infer_explicit_slots("지난달 대비 수출액은 2.1% 증가했다.")

    assert result.comparison == {"type": "MONTH_OVER_MONTH"}
    assert result.calculation == "GROWTH_RATE"
    assert result.condition is None


def test_infers_quarter_over_quarter_and_decrease_direction() -> None:
    result = infer_explicit_slots("수출액은 전분기 대비 2.1% 감소했다.")

    assert result.comparison == {"type": "QUARTER_OVER_QUARTER"}
    assert result.condition is None


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


def test_apply_explicit_slots_fills_only_missing_growth_contract_fields() -> None:
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="2024년 수출액은 전년 대비 8.2% 증가했다.",
        indicator="수출액",
        value=8.2,
        unit="%",
        time="2024",
        frequency="년",
        comparison={"reference_period": "전년"},
        calculation="GROWTH_RATE",
        condition={"release_status": "확정"},
        parse_status="AUTO_OK",
    )

    enriched = apply_explicit_slots(claim)

    assert enriched.comparison == {
        "reference_period": "전년",
        "type": "YEAR_OVER_YEAR",
    }
    assert enriched.condition == {
        "release_status": "확정",
        "direction": "INCREASE",
    }


def test_apply_explicit_slots_never_overwrites_provider_fields() -> None:
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="수출액은 전년 대비 8.2% 증가했다.",
        indicator="수출액",
        value=8.2,
        unit="%",
        time="2024",
        frequency="년",
        comparison={"type": "MONTH_OVER_MONTH"},
        calculation="GROWTH_RATE",
        condition={"direction": "DECREASE"},
        parse_status="AUTO_OK",
    )

    enriched = apply_explicit_slots(claim)

    assert enriched.comparison == {"type": "MONTH_OVER_MONTH"}
    assert enriched.condition == {"direction": "DECREASE"}


def test_apply_explicit_slots_uses_predicate_not_indicator_word_for_direction() -> None:
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="수출 증가율은 전년 대비 3% 하락했다.",
        indicator="수출 증가율",
        value=-3,
        unit="%",
        time="2024",
        frequency="년",
        calculation="GROWTH_RATE",
        parse_status="AUTO_OK",
    )

    enriched = apply_explicit_slots(claim)

    assert enriched.condition == {"direction": "DECREASE"}

def test_apply_explicit_slots_holds_multiple_comparison_clauses() -> None:
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="수출액은 전년 대비 3% 증가했지만 전월 대비 2% 감소했다.",
        indicator="수출액",
        value=3,
        unit="%",
        time="2024",
        frequency="월",
        calculation="GROWTH_RATE",
        parse_status="AUTO_OK",
    )

    enriched = apply_explicit_slots(claim)

    assert enriched.parse_status == "HOLD"
    assert enriched.parse_reason == "AMBIGUOUS_COMPARISON"
    assert enriched.comparison is None
    assert enriched.condition is None

def test_apply_explicit_slots_fills_missing_direct_calculation() -> None:
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="2024년 취업자 수는 2,800만 명이었다.",
        indicator="취업자 수",
        value=28_000_000,
        unit="명",
        time="2024",
        calculation=None,
        parse_status="AUTO_OK",
    )

    enriched = apply_explicit_slots(claim)

    assert enriched.calculation == "DIRECT_VALUE"

def test_apply_explicit_slots_keeps_existing_comparison_for_directional_wording() -> None:
    claim = ClaimSchema(
        claim_id="claim_existing_comparison",
        source_sentence="수출액은 지난해보다 31% 증가했다.",
        indicator="수출액",
        value=31,
        unit="%",
        time="2024년",
        calculation="GROWTH_RATE",
        comparison={"type": "YEAR_OVER_YEAR"},
        parse_status="AUTO_OK",
    )

    enriched = apply_explicit_slots(claim)

    assert enriched.parse_status == "AUTO_OK"
    assert enriched.comparison == {"type": "YEAR_OVER_YEAR"}
    assert enriched.condition == {"direction": "INCREASE"}

def test_apply_explicit_slots_splits_explicit_sex_and_age_from_population_into_dimension() -> None:
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="2024년 12월 서울 여성 15~29세 취업자 수는 10만 명이었다.",
        indicator="취업자 수",
        value=100_000,
        unit="명",
        time="2024년 12월",
        frequency="MONTHLY",
        region="서울",
        population="여성 15~29세",
        parse_status="AUTO_OK",
    )

    enriched = apply_explicit_slots(claim)

    assert enriched.dimension == {"sex": "여성", "age": "15~29세"}

def test_infers_share_of_total_from_explicit_total_possessive_phrase() -> None:
    result = infer_explicit_slots("2024년 12월 여성 취업자 수는 전체 취업자 수의 40%였다.")

    assert result.comparison == {
        "type": "SHARE_OF_TOTAL",
        "numerator": "여성 취업자 수",
        "denominator": "전체 취업자 수",
        "denominator_member": "전체",
    }
    assert result.calculation == "SHARE"
