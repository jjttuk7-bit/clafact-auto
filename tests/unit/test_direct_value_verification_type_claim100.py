from core.direct_value_verification_type import classify_direct_value_target


def test_current_value_followed_by_historical_high_is_record() -> None:
    result = classify_direct_value_target(
        "지난달 실업률은 3.8%로 2022년 1월 이후 가장 높았다.",
        target_expression="3.8%",
        unit="%",
        indicator="실업률",
    )
    assert result.type_code == "RECORD"


def test_current_region_value_followed_by_national_scope_is_rank() -> None:
    result = classify_direct_value_target(
        "서울 고용률은 70%로 전국에서 가장 높았다.",
        target_expression="70%",
        unit="%",
        indicator="고용률",
    )
    assert result.type_code == "RANK"


def test_level_before_first_change_remains_direct() -> None:
    result = classify_direct_value_target(
        "지난해 출생아 수는 24만2334명으로 9년 만에 처음 증가했다.",
        target_expression="24만2334명",
        unit="명",
        indicator="출생아 수",
    )
    assert result.type_code == "DIRECT_VALUE"
