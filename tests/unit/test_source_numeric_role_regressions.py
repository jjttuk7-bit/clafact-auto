from core.source_numeric_inventory import inventory_numeric_mentions
from core.source_numeric_role_classifier import classify_numeric_roles


def test_selects_tonne_and_place_units_as_grounded_targets() -> None:
    tonne = classify_numeric_roles(
        source_sentence="연 263만t까지 수출했다.",
        mentions=inventory_numeric_mentions("연 263만t까지 수출했다."),
        claim_value=2_630_000,
        claim_unit="t",
        indicator="수출량",
    )
    places = classify_numeric_roles(
        source_sentence="인구 감소 지역 4곳 중 3곳이 군 지역이다.",
        mentions=inventory_numeric_mentions("인구 감소 지역 4곳 중 3곳이 군 지역이다."),
        claim_value=4,
        claim_unit="곳",
        indicator="인구 감소 지역",
    )

    assert tonne.target_status == "TARGET_SELECTED"
    assert tonne.assignments[0].role == "대상값"
    assert places.target_status == "TARGET_SELECTED"
    assert [assignment.auto_target_eligible for assignment in places.assignments] == [True, False]


def test_does_not_attach_distant_change_predicate_to_earlier_level() -> None:
    source = "20대 인구는 2020년 703만명을 기록한 후 4년 연속 감소세다."

    result = classify_numeric_roles(
        source_sentence=source,
        mentions=inventory_numeric_mentions(source),
        claim_value=20,
        claim_unit="대",
        indicator="20대 인구",
    )

    assignments = {assignment.expression: assignment for assignment in result.assignments}
    assert assignments["20대"].role == "연령"
    assert assignments["703만명"].role != "증감값"
