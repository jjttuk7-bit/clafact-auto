from core.claim_applicability import annotate_result_rows, classify_result_applicability


def test_foreign_or_private_statistic_is_diagnostic_non_kosis_only() -> None:
    result = classify_result_applicability({
        "route_status": "HOLD",
        "source_sentence": "미 노동부가 지난달 소비자물가지수(CPI)가 2.3% 상승했다고 밝혔다.",
    })

    assert result["label"] == "LIKELY_NON_KOSIS_OR_PRIVATE"
    assert result["changes_pipeline_route"] is False


def test_relative_period_without_release_is_context_required() -> None:
    result = classify_result_applicability({
        "route_status": "HOLD",
        "source_sentence": "지난달 수출은 전년보다 1.8% 늘었다.",
    })

    assert result["label"] == "CONTEXT_REQUIRED"


def test_annotation_preserves_auto_and_hold_routes() -> None:
    rows = annotate_result_rows([
        {"claim_id": "a", "route_status": "AUTO", "source_sentence": "통계청이 3월 출생아 수를 발표했다."},
        {"claim_id": "b", "route_status": "HOLD", "source_sentence": "회사 매출 전망은 8%다."},
    ])

    assert [row["route_status"] for row in rows] == ["AUTO", "HOLD"]
    assert all("applicability_diagnosis" in row for row in rows)
