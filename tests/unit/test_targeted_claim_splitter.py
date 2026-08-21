from core.targeted_claim_splitter import build_targeted_claim_inputs


def test_targeted_splitter_emits_each_independently_verifiable_statistic_not_dates_or_ages() -> None:
    targets = build_targeted_claim_inputs(
        "20대 쉬었음 인구는 37만8000명으로 전년 동월 대비 1만2000명 늘었다."
    )

    assert [target.expression for target in targets] == ["37만8000명", "1만2000명"]
    assert all("target_numeric_expression" in target.extractor_input for target in targets)


def test_targeted_splitter_handles_index_level_and_growth_rate() -> None:
    targets = build_targeted_claim_inputs(
        "지난달 소비자물가지수는 116.31(2020년=100)로 작년 동월 대비 2.2% 올랐다."
    )

    assert [target.expression for target in targets] == ["116.31", "2.2%"]
