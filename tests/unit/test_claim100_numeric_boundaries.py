from core.direct_value_verification_type import classify_direct_value_target
from core.source_numeric_inventory import inventory_numeric_mentions
from core.source_numeric_role_classifier import classify_numeric_roles


def test_percentage_point_change_is_amount_not_growth_rate() -> None:
    result = classify_direct_value_target(
        "청년 고용률은 전년 동월 대비 1.5%포인트 감소했다.",
        target_expression="1.5%포인트",
        unit="%p",
        indicator="고용률",
    )
    assert result.type_code == "DIFFERENCE"


def test_parenthetical_historical_value_is_not_selected_as_current_target() -> None:
    source = "증가폭이 2023년(32만7000명)의 절반 아래로 줄었다."
    mentions = inventory_numeric_mentions(source)
    result = classify_numeric_roles(
        source_sentence=source,
        mentions=mentions,
        claim_value=327000,
        claim_unit="명",
        indicator="증가폭",
    )
    matching = [item for item in result.assignments if item.expression == "32만7000명"]
    assert len(matching) == 1
    assert matching[0].role == "비교값"
    assert matching[0].auto_target_eligible is False
