from core.direct_value_claim_reclassifier import reclassify_direct_value_claim


def _row(source: str, *, value: str, unit: str, calculation: str = "DIRECT_VALUE", reason: str = "CLAIM_PARSE_UNCERTAIN") -> dict[str, str]:
    return {
        "자식Claim번호": "C1",
        "원본부모Claim번호": "P1",
        "원문": source,
        "지표": "취업자",
        "기사값": value,
        "단위": unit,
        "기준시점": "2024-01",
        "주기": "월",
        "계산방식": calculation,
        "대상수치표현": "",
        "개선후사유": reason,
        "사용집합": "RULE_DISCOVERY",
    }


def test_observation_exclusions_win_before_type_classification() -> None:
    decision = reclassify_direct_value_claim(
        _row("내년 성장률은 2.1%로 전망된다.", value="2.1", unit="%")
    )
    assert decision.top_level_result == "EXCLUDE_FROM_KOSIS"
    assert decision.result_code == "EXCLUDE_FORECAST"


def test_change_amount_and_rate_move_to_owned_tabs() -> None:
    amount = reclassify_direct_value_claim(
        _row("취업자는 12만명 증가했다.", value="12", unit="만명")
    )
    rate = reclassify_direct_value_claim(
        _row("취업자는 전년보다 3.2% 증가했다.", value="3.2", unit="%")
    )
    assert (amount.top_level_result, amount.target_tab) == ("MOVE_TO_OTHER_TYPE", "6.증감량")
    assert (rate.top_level_result, rate.target_tab) == ("MOVE_TO_OTHER_TYPE", "7.증감률")


def test_share_record_and_rank_are_moved_not_forced_direct() -> None:
    share = reclassify_direct_value_claim(_row("고령층은 전체의 20%를 차지했다.", value="20", unit="%"))
    record = reclassify_direct_value_claim(_row("실업률은 3.8%로 역대 최고였다.", value="3.8", unit="%"))
    rank = reclassify_direct_value_claim(_row("서울 고용률은 70%로 전국에서 가장 높았다.", value="70", unit="%"))
    assert share.target_tab == "4.비중·구성비"
    assert record.target_tab == "5.최고·최저"
    assert rank.target_tab == "순위"


def test_exact_level_stays_in_direct_lane_with_source_evidence() -> None:
    decision = reclassify_direct_value_claim(
        _row("2024년 1월 취업자는 2,800만명이었다.", value="2800", unit="만명")
    )
    assert decision.top_level_result == "KEEP_DIRECT_VALUE"
    assert decision.result_code == "KEEP_DIRECT_RECOVERED"
    assert "2,800만명" in decision.source_evidence


def test_ambiguous_target_fails_closed_in_direct_recovery_lane() -> None:
    decision = reclassify_direct_value_claim(
        _row("취업자는 11만명이고 실업자는 10만명이다.", value="12", unit="만명")
    )
    assert decision.top_level_result == "KEEP_DIRECT_VALUE"
    assert decision.result_code == "KEEP_DIRECT_REQUIRES_RECOVERY"


def test_missing_source_percentage_point_change_falls_back_to_amount() -> None:
    decision = reclassify_direct_value_claim(
        _row(
            "고용률은 감소했다.",
            value="1.5",
            unit="%p",
            reason="DIRECT_VALUE_CHANGE_TARGET_MISCLASSIFIED",
        )
    )
    assert decision.target_tab == "6.증감량"
