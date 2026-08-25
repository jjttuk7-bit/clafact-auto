from core.source_numeric_inventory import (
    digit_positions_not_covered,
    inventory_numeric_mentions,
)


def test_inventories_truncated_and_malformed_numeric_expressions() -> None:
    source = "출생자는 202...명이고 수출은 70... 수준, 증가율은 15.%였다."

    mentions = inventory_numeric_mentions(source)

    assert [mention.expression for mention in mentions] == ["202...", "70...", "15.%"]
    assert digit_positions_not_covered(source, mentions) == []


def test_inventories_model_version_digits_after_period() -> None:
    source = "2025년형 ID.4의 가격은 ID.4 Pro가 5999만원이다."

    mentions = inventory_numeric_mentions(source)

    assert [mention.expression for mention in mentions] == ["2025년", "4", "4", "5999만원"]
    assert digit_positions_not_covered(source, mentions) == []
