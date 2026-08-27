from core.direct_value_claim_reclassification_results import (
    compile_reclassifications,
    merge_reclassifications,
    summarize_reclassifications,
)


def _row(claim_id: str, reason: str, source: str, value: str, unit: str) -> dict[str, str]:
    return {
        "원본부모Claim번호": claim_id,
        "자식Claim번호": claim_id,
        "개선후사유": reason,
        "사용집합": "RULE_DISCOVERY",
        "원문": source,
        "지표": "취업자",
        "기사값": value,
        "단위": unit,
        "기준시점": "2024",
        "주기": "년",
        "계산방식": "DIRECT_VALUE",
        "대상수치표현": "",
    }


def test_compile_merge_and_summary_preserve_exact_scope() -> None:
    rows = [
        _row("C1", "CLAIM_PARSE_UNCERTAIN", "취업자는 10만명 증가했다.", "10", "만명"),
        _row("C2", "NON_OBSERVED_FORECAST", "성장률은 2%로 전망된다.", "2", "%"),
        _row("C3", "NO_HARD_GUARD_CANDIDATE", "취업자는 20만명이다.", "20", "만명"),
    ]
    results = compile_reclassifications(rows, expected_count=2)
    merged = merge_reclassifications(rows, results, evidence_ref="audit.json")
    summary = summarize_reclassifications(results)

    assert len(merged) == 3
    assert sum(summary["top_level_counts"].values()) == 2
    assert merged[0]["이동대상탭"] == "6.증감량"
    assert merged[1]["Claim구조상위결과"] == "EXCLUDE_FROM_KOSIS"
    assert merged[2]["Claim구조재판정실행"] == ""
