from core.targeted_claim_splitter import (
    build_targeted_claim_inputs,
    discover_numeric_mentions,
)


def test_discovers_mentions_without_creating_children() -> None:
    mentions = discover_numeric_mentions(
        "고용률은 60%로 전년 58%보다 2%포인트 올랐다."
    )

    assert [mention.mention_id for mention in mentions] == ["n1", "n2", "n3"]
    assert [mention.expression for mention in mentions] == [
        "60%",
        "58%",
        "2%포인트",
    ]


def test_targeted_splitter_emits_each_independently_verifiable_statistic_not_dates_or_ages() -> None:
    targets = build_targeted_claim_inputs(
        "20대 쉬었음 인구는 37만8000명으로 전년 동월 대비 1만2000명 늘었다."
    )

    assert [target.expression for target in targets] == ["37만8000명", "1만2000명"]
    assert all("target_numeric_expression" in target.extractor_input for target in targets)


def test_coordinated_age_groups_are_not_treated_as_vehicle_counts() -> None:
    sentence = "40대와 50대 취업자 수가 각각 4만9000명, 2만6000명 줄었다."

    mentions = discover_numeric_mentions(sentence)

    assert [mention.expression for mention in mentions] == ["4만9000명", "2만6000명"]


def test_targeted_splitter_handles_index_level_and_growth_rate() -> None:
    targets = build_targeted_claim_inputs(
        "지난달 소비자물가지수는 116.31(2020년=100)로 작년 동월 대비 2.2% 올랐다."
    )

    assert [target.expression for target in targets] == ["116.31(2020년=100)", "2.2%"]


def test_discovers_vehicle_counts_with_spaced_korean_scale() -> None:
    mentions = discover_numeric_mentions(
        "KG모빌리티도 18.2% 늘어난 6만 2378대를 수출했다."
    )

    assert [mention.expression for mention in mentions] == ["18.2%", "6만2378대"]


def test_discovers_fullwidth_percent_and_compound_vehicle_count() -> None:
    mentions = discover_numeric_mentions(
        "수입 승용차 판매량은 26만3288대로 전년 대비 2.9％ 줄었다."
    )

    assert [mention.expression for mention in mentions] == ["26만3288대", "2.9％"]


def test_preserves_negative_signs_for_separate_rates() -> None:
    mentions = discover_numeric_mentions(
        "현대차(-0.5%), 르노코리아(-18.4%) 판매가 줄었다."
    )

    assert [mention.expression for mention in mentions] == ["-0.5%", "-18.4%"]


def test_discovers_multiple_historical_counts_without_treating_years_as_values() -> None:
    mentions = discover_numeric_mentions(
        "판매량은 1996년 1만315대, 1997년 8136대, 1998년 2075대였다."
    )

    assert [mention.expression for mention in mentions] == [
        "1만315대",
        "8136대",
        "2075대",
    ]
