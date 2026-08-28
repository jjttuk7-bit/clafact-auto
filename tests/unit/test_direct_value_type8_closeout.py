import pytest

from core.direct_value_type8_closeout import merge_type8_closeout


def _base(claim_id: str, *, complete: str = "N") -> dict[str, object]:
    return {
        "자식Claim번호": claim_id,
        "원문": f"{claim_id} 원문",
        "최종상태": "AUTO" if complete == "Y" else "HOLD",
        "최종사유코드": "WITHIN_TOLERANCE" if complete == "Y" else "OLD_REASON",
        "실패단계": "완료" if complete == "Y" else "필수 조건 검사",
        "판정": "MATCH" if complete == "Y" else "",
        "공식계산값": "1.0" if complete == "Y" else "",
        "공식좌표JSON": '[{"canonical_key":"OLD"}]' if complete == "Y" else "[]",
        "공식근거URL": "https://kosis.kr/old" if complete == "Y" else "",
        "응답해시": "old-hash" if complete == "Y" else "",
        "공표확인": "VERIFIED" if complete == "Y" else "",
        "공식근거종류": "KOSIS_API" if complete == "Y" else "",
        "공식판정완료": complete,
    }


def _update(claim_id: str, source: str, *, complete: bool, reason: str) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "source": source,
        "terminal_status": "AUTO" if complete else "HOLD",
        "reason_code": reason,
        "failure_stage": "완료" if complete else "공식값 조회",
        "verdict": "MATCH" if complete else "UNDETERMINED",
        "official_values": [1.0] if complete else [],
        "evidence_cells": [{"canonical_key": "K1"}] if complete else [],
        "provenance": [{
            "evidence_key": "K1",
            "source": "API",
            "source_url": "https://kosis.kr/new",
            "content_hash": "new-hash",
            "retrieved_at": "2026-08-28T00:00:00Z",
            "publication": {"status": "VERIFIED"},
        }] if complete else [],
    }


def test_closeout_preserves_230_order_and_latest_94_takes_precedence() -> None:
    base = [_base("C1"), _base("C2", complete="Y"), _base("C3")]
    run176 = [_update("C1", "176", complete=True, reason="WITHIN_TOLERANCE")]
    run94 = [_update("C1", "94", complete=False, reason="AS_OF_UNAVAILABLE")]

    result = merge_type8_closeout(base, run176, run94, expected_count=3)

    assert [row["자식Claim번호"] for row in result.rows] == ["C1", "C2", "C3"]
    assert result.rows[0]["8번최종결과출처"] == "94"
    assert result.rows[0]["8번엄격공식판정완료"] == "N"
    assert result.rows[1]["8번엄격공식판정완료"] == "Y"
    assert result.summary["strict_official_complete_count"] == 1
    assert result.summary["source_counts"] == {"230_BASE": 2, "94": 1}


def test_closeout_accepts_new_official_result_only_with_complete_evidence_contract() -> None:
    valid = _update("C1", "176", complete=True, reason="WITHIN_TOLERANCE")
    invalid = _update("C2", "176", complete=True, reason="WITHIN_TOLERANCE")
    invalid["provenance"] = [{**invalid["provenance"][0], "content_hash": ""}]

    result = merge_type8_closeout([_base("C1"), _base("C2")], [valid, invalid], [], expected_count=2)

    assert result.rows[0]["8번엄격공식판정완료"] == "Y"
    assert result.rows[1]["8번엄격공식판정완료"] == "N"
    assert result.summary["strict_official_complete_count"] == 1


def test_closeout_rejects_unknown_or_duplicate_claim_ids() -> None:
    with pytest.raises(ValueError, match="TYPE8_BASE_ID_INVALID"):
        merge_type8_closeout([_base("C1"), _base("C1")], [], [], expected_count=2)
    with pytest.raises(ValueError, match="TYPE8_UPDATE_OUTSIDE_SCOPE"):
        merge_type8_closeout([_base("C1")], [_update("C2", "176", complete=False, reason="X")], [], expected_count=1)
