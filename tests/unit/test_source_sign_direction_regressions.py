from core.source_sign_direction import assess_source_sign_direction


def _decision(
    source: str,
    expression: str,
    *,
    value: float,
    condition: dict[str, str] | None = None,
):
    start = source.index(expression)
    return assess_source_sign_direction(
        source_sentence=source,
        indicator="취업자 수",
        value=value,
        target_expression=expression,
        target_role="증감값",
        target_start=start,
        target_end=start + len(expression),
        stored_condition=condition,
    )


def test_corrects_direction_from_exact_target_not_later_claim() -> None:
    source = "전체 취업자 수가 31만명 이상 늘었지만 청년층은 14만6000명 줄었다."
    decision = _decision(
        source,
        "31만명",
        value=310_000,
        condition={"direction": "DECREASE", "operator": "GTE"},
    )

    assert decision.status == "STORED_DIRECTION_CONFLICT_CORRECTED"
    assert decision.source_direction == "INCREASE"
    assert decision.signed_target_value == 310_000
    assert "늘" in decision.basis_text


def test_semantic_change_head_wins_over_later_reduction_of_growth_width() -> None:
    source = "증가폭이 2023년(32만7000명)의 절반 아래로 줄었다."
    decision = _decision(
        source,
        "32만7000명",
        value=327_000,
        condition={"direction": "DECREASE"},
    )

    assert decision.source_direction == "INCREASE"
    assert decision.status == "STORED_DIRECTION_CONFLICT_CORRECTED"
    assert decision.signed_target_value == 327_000


def test_blocks_level_endpoint_or_peak_misclassified_as_change_amount() -> None:
    peak = _decision(
        "생산연령인구는 2017년(3686만명)을 정점으로 하락세로 돌아섰다.",
        "3686만명",
        value=36_860_000,
        condition={"direction": "DECREASE"},
    )
    endpoint = _decision(
        "대미 수출을 지난해 42만대까지 늘렸다.",
        "42만대",
        value=420_000,
    )

    assert peak.status == "TARGET_ROLE_REVIEW_REQUIRED"
    assert endpoint.status == "TARGET_ROLE_REVIEW_REQUIRED"


def test_accepts_repeated_same_trade_balance_polarity() -> None:
    source = "무역 수지도 518억 달러 흑자로 3년 만에 흑자로 돌아섰다."
    expression = "518억 달러"
    start = source.index(expression)

    decision = assess_source_sign_direction(
        source_sentence=source,
        indicator="무역수지",
        value=51_800_000_000,
        target_expression=expression,
        target_role="대상값",
        target_start=start,
        target_end=start + len(expression),
        stored_condition=None,
    )

    assert decision.status == "BALANCE_POLARITY_CONFIRMED"
    assert decision.source_polarity == "SURPLUS"
    assert decision.signed_target_value == 51_800_000_000


def test_supports_change_predicate_conjunction_endings_from_actual_rows() -> None:
    decrease = _decision(
        "제조업 취업자는 7만4000명 줄며 감소세가 이어졌다.",
        "7만4000명",
        value=74_000,
        condition={"direction": "DECREASE"},
    )
    increase = _decision(
        "취업자 수는 매월 10만명 이상 늘고 있다.",
        "10만명",
        value=100_000,
        condition={"direction": "INCREASE"},
    )

    assert decrease.status == "SIGN_DIRECTION_CONFIRMED"
    assert decrease.signed_target_value == -74_000
    assert increase.status == "SIGN_DIRECTION_CONFIRMED"
    assert increase.signed_target_value == 100_000
