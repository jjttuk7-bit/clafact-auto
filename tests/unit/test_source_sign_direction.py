from core.source_sign_direction import assess_source_sign_direction


def _assess(
    source: str,
    expression: str,
    *,
    indicator: str = "취업자 수",
    value: float = 35_000,
    role: str = "증감값",
    condition: dict[str, str] | None = None,
):
    start = source.index(expression)
    return assess_source_sign_direction(
        source_sentence=source,
        indicator=indicator,
        value=value,
        target_expression=expression,
        target_role=role,
        target_start=start,
        target_end=start + len(expression),
        stored_condition=condition,
    )


def test_recovers_missing_increase_and_decrease_without_changing_original_value() -> None:
    increase = _assess("취업자 수가 3만5000명 늘어났다.", "3만5000명")
    decrease = _assess(
        "지난달 수출은 전년 동월 대비 10.3% 급감했다.",
        "10.3%",
        indicator="수출액",
        value=10.3,
    )

    assert increase.status == "SOURCE_DIRECTION_RECOVERED"
    assert increase.source_direction == "INCREASE"
    assert increase.original_value == 35_000
    assert increase.signed_target_value == 35_000
    assert decrease.source_direction == "DECREASE"
    assert decrease.original_value == 10.3
    assert decrease.signed_target_value == -10.3


def test_confirms_trade_balance_polarity_and_separate_signed_value() -> None:
    deficit = _assess(
        "연간 누계 무역 수지는 10억5600만달러 적자다.",
        "10억5600만달러",
        indicator="무역수지",
        value=1_056_000_000,
        role="대상값",
    )
    surplus = _assess(
        "지난달 무역 수지는 35억달러 흑자였다.",
        "35억달러",
        indicator="무역수지",
        value=3_500_000_000,
        role="대상값",
    )

    assert deficit.status == "BALANCE_POLARITY_CONFIRMED"
    assert deficit.source_polarity == "DEFICIT"
    assert deficit.signed_target_value == -1_056_000_000
    assert surplus.source_polarity == "SURPLUS"
    assert surplus.signed_target_value == 3_500_000_000


def test_level_value_with_other_change_is_not_signed() -> None:
    decision = _assess(
        "취업자 수는 2804만1000명으로 전년 동월 대비 5만2000명 감소했다.",
        "2804만1000명",
        value=28_041_000,
        role="대상값",
        condition={"direction": "DECREASE"},
    )

    assert decision.status == "NOT_APPLICABLE_LEVEL_VALUE"
    assert decision.signed_target_value is None
