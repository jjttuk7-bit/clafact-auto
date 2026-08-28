from core.direct_value_coordinate_94_analysis import analyze_coordinate_94
from core.direct_value_coordinate_94_scope import build_coordinate_94_scope


def test_analysis_classifies_every_scope_claim_with_evidence() -> None:
    evaluation = [{
        "Claim번호": "C1",
        "원문": "2024년 수입액은 10억원이다.",
        "최종실패단계": "필수 조건 검사",
        "최종사유": "NO_HARD_GUARD_CANDIDATE",
        "검색지표": "수입액",
        "단위": "원",
        "주기": "년",
        "지역": "전국",
        "대상집단": "",
    }]
    scope = build_coordinate_94_scope(evaluation, expected_count=1)
    live = [{
        "parent_claim_id": "C1",
        "claim": {
            "claim_id": "C1",
            "source_sentence": evaluation[0]["원문"],
            "indicator": "수입액",
            "unit": "원",
            "time": "2024",
            "frequency": "년",
            "region": "전국",
        },
        "official_resolution": {
            "catalog_diagnostics": {"hard_guard_best_reject_UNIT_CONFLICT": 1},
            "candidates": [{
                "tbl_id": "T1",
                "tbl_name": "수입액",
                "core_item_names": ["수입액"],
                "unit_names": ["억원"],
            }],
        },
    }]

    analysis = analyze_coordinate_94(scope, live)

    assert len(analysis.rows) == 1
    assert analysis.rows[0]["대표원인"] == "UNIT_COORDINATE_GAP"
    assert analysis.rows[0]["적용규칙군"] == "SAME_MEASURE_UNIT_SCALE"
    assert analysis.primary_cause_counts == {"UNIT_COORDINATE_GAP": 1}


def test_analysis_rejects_missing_or_duplicate_live_claims() -> None:
    evaluation = [{
        "Claim번호": "C1", "원문": "값은 1명이다.",
        "최종실패단계": "필수 조건 검사", "최종사유": "NO_HARD_GUARD_CANDIDATE",
        "검색지표": "인구", "단위": "명", "주기": "년", "지역": "전국", "대상집단": "",
    }]
    scope = build_coordinate_94_scope(evaluation, expected_count=1)

    try:
        analyze_coordinate_94(scope, [])
    except ValueError as error:
        assert str(error) == "DIRECT_VALUE_COORDINATE_94_LIVE_MISSING:C1"
    else:
        raise AssertionError("missing live row must fail")
