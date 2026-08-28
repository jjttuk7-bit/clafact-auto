from tools.compile_direct_value_type8_closeout import normalize_update


def test_normalize_update_combines_evaluation_and_canonical_live_result() -> None:
    evaluation = {
        "Claim번호": "C1",
        "최종경로": "AUTO",
        "최종판정": "MATCH",
        "최종사유": "WITHIN_TOLERANCE",
        "최종실패단계": "완료",
    }
    live = {
        "claim_id": "C1",
        "official_resolution": {
            "verdict": {
                "verdict": "MATCH",
                "evidence_values": [10.0],
                "evidence_cells": [{"canonical_key": "K1"}],
                "official_value_provenance": [{
                    "evidence_key": "K1",
                    "source": "API",
                    "source_url": "https://kosis.kr/value",
                    "content_hash": "hash",
                    "retrieved_at": "2026-08-28T00:00:00Z",
                    "publication": {"status": "VERIFIED"},
                }],
            }
        },
    }

    update = normalize_update(evaluation, live, source="176_CANONICAL_RUN")

    assert update["claim_id"] == "C1"
    assert update["terminal_status"] == "AUTO"
    assert update["official_values"] == [10.0]
    assert update["evidence_cells"][0]["canonical_key"] == "K1"
    assert update["provenance"][0]["content_hash"] == "hash"


def test_normalize_update_uses_evaluation_status_but_does_not_invent_evidence() -> None:
    evaluation = {
        "Claim번호": "C2",
        "최종경로": "HOLD",
        "최종판정": "UNDETERMINED",
        "최종사유": "NO_DATA",
        "최종실패단계": "공식값 조회",
    }

    update = normalize_update(evaluation, {"claim_id": "C2"}, source="94_COMMON_RULE_RERUN")

    assert update["terminal_status"] == "HOLD"
    assert update["reason_code"] == "NO_DATA"
    assert update["official_values"] == []
    assert update["provenance"] == []
