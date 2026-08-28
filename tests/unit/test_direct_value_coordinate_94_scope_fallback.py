from core.direct_value_coordinate_94_scope import build_coordinate_94_scope


def test_scope_uses_live_source_fallback_for_blind_evaluation_row() -> None:
    row = {
        "Claim번호": "C1",
        "원문": "",
        "최종실패단계": "필수 조건 검사",
        "최종사유": "NO_HARD_GUARD_CANDIDATE",
        "검색지표": "인구",
        "단위": "명",
        "주기": "년",
        "지역": "전국",
        "대상집단": "",
    }

    scope = build_coordinate_94_scope(
        [row],
        expected_count=1,
        source_fallbacks={"C1": "2024년 총인구는 100만명이다."},
    )

    assert scope.records[0].source_sentence == "2024년 총인구는 100만명이다."
