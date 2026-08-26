from core.targeted_claim_splitter import discover_numeric_mentions


def test_does_not_truncate_duration_months_to_item_count() -> None:
    mentions = discover_numeric_mentions(
        "취업자 수는 3년 10개월 만에 감소세로 돌아섰다."
    )

    assert mentions == []


def test_discovers_plain_index_level_only_with_explicit_index_context() -> None:
    sentence = "지난달 소비자물가 지수는 116.38로 전년 동월 대비 2.1% 올랐다."

    mentions = discover_numeric_mentions(sentence)

    assert [mention.expression for mention in mentions] == ["116.38", "2.1%"]
    assert [sentence[item.start:item.end] for item in mentions] == ["116.38", "2.1%"]


def test_preserves_long_units_and_ratio_operands() -> None:
    mentions = discover_numeric_mentions(
        "지난달 취업자 10명 중 1명이고 고용률은 0.7%포인트 올랐다."
    )

    assert [mention.expression for mention in mentions] == [
        "10명",
        "1명",
        "0.7%포인트",
    ]
