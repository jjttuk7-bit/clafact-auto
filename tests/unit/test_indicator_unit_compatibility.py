from core.indicator_unit_compatibility import assess_indicator_unit


def test_accepts_matching_level_indicator_and_unit_families() -> None:
    cases = [
        ("취업자 수", "명", "대상값"),
        ("수출액", "달러", "대상값"),
        ("고용률", "%", "대상값"),
        ("수출량", "톤", "대상값"),
        ("농가 수", "가구", "대상값"),
        ("과수원 면적", "ha", "대상값"),
    ]

    for indicator, unit, role in cases:
        decision = assess_indicator_unit(indicator, unit, role)
        assert decision.status == "COMPATIBLE", (indicator, unit, decision)


def test_separates_indicator_refinement_from_hard_conflict() -> None:
    trade_quantity = assess_indicator_unit("수출액", "대", "대상값")
    population_money = assess_indicator_unit("총인구", "원", "대상값")
    growth_count = assess_indicator_unit("경제성장률", "개", "대상값")

    assert trade_quantity.status == "INDICATOR_REFINEMENT_REQUIRED"
    assert trade_quantity.suggested_indicator == "수출대수"
    assert population_money.status == "INDICATOR_UNIT_CONFLICT"
    assert growth_count.status == "INDICATOR_UNIT_CONFLICT"


def test_relative_change_percent_requires_refinement_not_unit_conflict() -> None:
    people_change = assess_indicator_unit("취업자 수", "%", "증감값")
    export_change = assess_indicator_unit("수출액", "%", "증감값")
    rate_point_change = assess_indicator_unit("고용률", "%p", "증감값")

    assert people_change.status == "INDICATOR_REFINEMENT_REQUIRED"
    assert people_change.suggested_indicator == "취업자 수 증감률"
    assert export_change.status == "INDICATOR_REFINEMENT_REQUIRED"
    assert rate_point_change.status == "COMPATIBLE"


def test_refines_known_composite_production_percent() -> None:
    decision = assess_indicator_unit("전산업생산", "%", "대상값")

    assert decision.status == "INDICATOR_REFINEMENT_REQUIRED"
    assert decision.suggested_indicator == "전산업생산 증감률"
