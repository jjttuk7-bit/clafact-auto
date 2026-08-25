from core.source_numeric_inventory import (
    digit_positions_not_covered,
    inventory_numeric_mentions,
)


def _expressions(source: str) -> list[str]:
    return [mention.expression for mention in inventory_numeric_mentions(source)]


def test_inventories_every_number_in_mixed_news_sentence() -> None:
    source = "보잉 737 맥스 사고로 189명이 사망한 2018년(전체 사망자 526명) 이후 가장 많다."

    mentions = inventory_numeric_mentions(source)

    assert [mention.expression for mention in mentions] == ["737", "189명", "2018년", "526명"]
    assert all(source[mention.start:mention.end] == mention.expression for mention in mentions)
    assert digit_positions_not_covered(source, mentions) == []


def test_preserves_ranges_compound_scales_and_signs() -> None:
    source = "성장률은 3~4%였고 취업자는 -47만3000명, 전체는 2804만1000명이었다."

    assert _expressions(source) == ["3~4%", "-47만3000명", "2804만1000명"]


def test_inventories_dates_ages_ranks_and_lexical_quantities() -> None:
    source = "2025-01-15 기준 20대 인구는 상위 7개 지역에서 석 달 새 2.1배가 됐다."

    assert _expressions(source) == ["2025-01-15", "20대", "7개", "석 달", "2.1배"]


def test_inventories_index_basis_as_separate_atomic_mentions() -> None:
    source = "소비자물가지수는 116.31(2020년=100)이다."

    assert _expressions(source) == ["116.31", "2020년", "100"]

