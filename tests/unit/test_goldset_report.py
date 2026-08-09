from core.goldset_report import classify_hold_reason, summarize_goldset


def test_classify_hold_reason_maps_asof_revision_to_official_value_unavailable() -> None:
    assert classify_hold_reason("기사 시점 스냅샷 미확보·사후 개정") == "ARTICLE_TIME_OFFICIAL_VALUE_UNAVAILABLE"


def test_summarize_goldset_creates_complete_route_counts() -> None:
    records = [
        {"claim_id": "A", "KOSIS_재현_상태": "KOSIS 재현 가능"},
        {"claim_id": "B", "KOSIS_재현_상태": "KOSIS 재현 불가", "판정불가_유형": "KOSIS 표·좌표 미확보"},
    ]

    report = summarize_goldset(records)

    assert report["summary"] == {"total": 2, "AUTO": 1, "HOLD": 1, "HUMAN_REVIEW": 0}
    assert report["results"][1]["hold_category"] == "EVIDENCE_CELL_UNRESOLVED"
