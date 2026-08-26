from core.indicator_unit_compatibility import assess_indicator_unit


def test_accepts_dependency_ratio_people_and_dual_scale_people() -> None:
    dependency = assess_indicator_unit("노년부양비", "명", "대상값")
    irregular = assess_indicator_unit("비정규직 규모/비율", "명", "대상값")

    assert dependency.status == "COMPATIBLE"
    assert irregular.status == "COMPATIBLE"


def test_refines_currency_point_and_composite_percent_instead_of_conflict() -> None:
    contribution = assess_indicator_unit("수출액", "%p", "대상값")
    construction = assess_indicator_unit("건설투자", "%", "대상값")

    assert contribution.status == "INDICATOR_REFINEMENT_REQUIRED"
    assert construction.status == "INDICATOR_REFINEMENT_REQUIRED"


def test_does_not_assume_gdp_percent_is_growth_rate_without_change_role() -> None:
    decision = assess_indicator_unit("GDP", "%", "대상값")

    assert decision.status == "REVIEW_REQUIRED"
    assert decision.suggested_indicator == ""


def test_rejects_index_item_count_as_measure_conflict() -> None:
    decision = assess_indicator_unit("소비자물가지수", "개", "대상값")

    assert decision.status == "INDICATOR_UNIT_CONFLICT"
