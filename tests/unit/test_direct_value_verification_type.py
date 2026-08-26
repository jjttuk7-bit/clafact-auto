from core.direct_value_verification_type import classify_direct_value_target


def test_amount_change_is_moved_to_difference_type() -> None:
    result = classify_direct_value_target(
        "지난달 취업자 수가 13만5000명 늘었다.",
        target_expression="13만5000명",
        unit="명",
        indicator="취업자 수",
    )

    assert result.type_code == "DIFFERENCE"
    assert result.reason_code == "RECLASSIFY_TO_DIFFERENCE"


def test_percent_change_is_moved_to_growth_rate_type() -> None:
    result = classify_direct_value_target(
        "지난달 수출은 전년 동월 대비 10.3% 급감했다.",
        target_expression="10.3%",
        unit="%",
        indicator="수출액",
    )

    assert result.type_code == "GROWTH_RATE"
    assert result.reason_code == "RECLASSIFY_TO_GROWTH_RATE"


def test_record_statement_is_moved_to_record_type() -> None:
    result = classify_direct_value_target(
        "1분기 기준으로는 2008년 377만8000톤 이후 17년 만에 최대 수입량이다.",
        target_expression="377만8000톤",
        unit="톤",
        indicator="수입량",
    )

    assert result.type_code == "RECORD"
    assert result.reason_code == "RECLASSIFY_TO_RECORD"


def test_level_value_remains_direct() -> None:
    result = classify_direct_value_target(
        "지난달 ICT 무역 수지는 58억1000만달러 흑자를 기록했다.",
        target_expression="58억1000만달러",
        unit="달러",
        indicator="무역수지",
    )

    assert result.type_code == "DIRECT_VALUE"
    assert result.reason_code is None


def test_rate_level_remains_direct_when_no_change_relation_exists() -> None:
    result = classify_direct_value_target(
        "지난 1분기 30대 대졸 이상 실업률은 2.4%였다.",
        target_expression="2.4%",
        unit="%",
        indicator="실업률",
    )

    assert result.type_code == "DIRECT_VALUE"
    assert result.reason_code is None


def test_share_statement_is_moved_to_share_type() -> None:
    result = classify_direct_value_target(
        "고령층이 전체 인구의 20%를 차지했다.",
        target_expression="20%",
        unit="%",
        indicator="고령층 비중",
    )

    assert result.type_code == "SHARE"
    assert result.reason_code == "RECLASSIFY_TO_SHARE"


def test_direct_level_is_not_moved_only_because_sentence_also_mentions_record() -> None:
    result = classify_direct_value_target(
        "지난해 출생아 수는 24만2334명으로 9년 만에 처음 증가했다.",
        target_expression="24만2334명",
        unit="명",
        indicator="출생아 수",
    )

    assert result.type_code == "DIRECT_VALUE"
    assert result.reason_code is None


def test_historical_operand_followed_by_since_is_record_context() -> None:
    result = classify_direct_value_target(
        "취업자는 2021년 2월 -47만3000명 이후 3년 10개월 만에 감소했다.",
        target_expression="-47만3000명",
        unit="명",
        indicator="취업자 수",
    )

    assert result.type_code == "RECORD"