from core.direct_value_generalization_split import split_claim_rows


def test_split_tracks_requested_claim_ratios_for_many_articles() -> None:
    rows = [
        {
            "원본부모Claim번호": f"A{index:05d}_1",
            "자식Claim번호": f"c{index}",
            "지표": "취업자",
            "단위": "명",
            "주기": "월",
            "최종사유코드": "NO_EVIDENCE_COORDINATE_CANDIDATE",
        }
        for index in range(230)
    ]

    split = split_claim_rows(rows)
    counts = {
        name: sum(item.split_set == name for item in split)
        for name in {
            "RULE_DISCOVERY",
            "INTERMEDIATE_VALIDATION",
            "FINAL_BLIND",
        }
    }

    assert abs(counts["RULE_DISCOVERY"] - 161) <= 1
    assert abs(counts["INTERMEDIATE_VALIDATION"] - 46) <= 1
    assert abs(counts["FINAL_BLIND"] - 23) <= 1
