from tools.compile_direct_value_type8_closeout import _updates


def test_updates_allows_preverification_rows_without_live_pipeline_result() -> None:
    evaluations = [
        {"Claim번호": "C1", "최종경로": "PRE_VERIFICATION", "최종사유": "MISSING_TIME"},
        {"Claim번호": "C2", "최종경로": "HOLD", "최종사유": "NO_DATA"},
    ]
    live_rows = [{"claim_id": "C2", "official_resolution": None}]

    updates = _updates(evaluations, live_rows, source="176_CANONICAL_RUN", expected_count=2)

    assert [row["claim_id"] for row in updates] == ["C1", "C2"]
    assert updates[0]["terminal_status"] == "PRE_VERIFICATION"
    assert updates[0]["official_values"] == []
