import pytest

from core.direct_value_coordinate_94_scope import build_coordinate_94_scope


def _row(claim_id: str, *, stage: str = "필수 조건 검사") -> dict[str, str]:
    return {
        "Claim번호": claim_id,
        "원문": f"{claim_id}의 값은 1명이다.",
        "최종실패단계": stage,
        "최종사유": "NO_HARD_GUARD_CANDIDATE",
        "검색지표": "인구",
        "단위": "명",
        "주기": "년",
        "지역": "전국",
        "대상집단": "",
    }


def test_scope_selects_only_hard_guard_failure_rows() -> None:
    scope = build_coordinate_94_scope(
        [_row("C2"), _row("C1"), _row("OTHER", stage="공식값 조회")],
        expected_count=2,
    )

    assert [record.claim_id for record in scope.records] == ["C1", "C2"]
    assert scope.failure_reason_counts == {"NO_HARD_GUARD_CANDIDATE": 2}
    assert len(scope.manifest_sha256) == 64
    assert all(len(record.source_sentence_sha256) == 64 for record in scope.records)


def test_scope_rejects_duplicate_claim_ids() -> None:
    with pytest.raises(ValueError, match="DIRECT_VALUE_COORDINATE_94_CLAIM_NOT_UNIQUE:C1"):
        build_coordinate_94_scope([_row("C1"), _row("C1")], expected_count=2)


def test_scope_rejects_incomplete_expected_count() -> None:
    with pytest.raises(ValueError, match="DIRECT_VALUE_COORDINATE_94_SCOPE_COUNT_MISMATCH:1:2"):
        build_coordinate_94_scope([_row("C1")], expected_count=2)


def test_scope_rejects_missing_source_or_claim_id() -> None:
    missing_source = _row("C1")
    missing_source["원문"] = ""
    with pytest.raises(ValueError, match="DIRECT_VALUE_COORDINATE_94_SOURCE_MISSING:C1"):
        build_coordinate_94_scope([missing_source], expected_count=1)

