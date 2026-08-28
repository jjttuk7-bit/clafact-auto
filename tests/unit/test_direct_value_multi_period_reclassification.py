from core.direct_value_claim_reclassifier import reclassify_direct_value_claim


def test_same_value_bound_to_two_explicit_years_requires_split() -> None:
    row = {
        "자식Claim번호": "C1",
        "원본부모Claim번호": "P1",
        "원문": "지난 2021년과 2022년에도 순수출의 성장 기여도는 0% 수준이었다.",
        "지표": "수출액",
        "기사값": "0",
        "단위": "%",
        "기준시점": "2021",
        "주기": "Y",
        "계산방식": "DIRECT_VALUE",
        "대상수치표현": "0%",
        "개선후사유": "INDICATOR_REFINEMENT_REQUIRED",
        "사용집합": "RULE_DISCOVERY",
    }

    decision = reclassify_direct_value_claim(row)

    assert decision.top_level_result == "MOVE_TO_RECOVERY"
    assert decision.result_code == "MOVE_MULTI_PERIOD_SPLIT"
    assert decision.target_tab == "복수 Claim 분리"
