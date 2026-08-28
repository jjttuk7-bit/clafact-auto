import pytest

from core.direct_value_coordinate_94_comparison import compile_coordinate94_comparison


def _before(claim_id: str) -> dict[str, object]:
    return {"Claim번호": claim_id, "최종실패단계": "필수 조건 검사", "최종사유": "OLD"}


def _after(claim_id: str, stage: str, reason: str, strict: str = "N") -> dict[str, object]:
    return {
        "Claim번호": claim_id,
        "최종실패단계": stage,
        "최종사유": reason,
        "엄격공식판정완료": strict,
        "검색지표": "취업자 수",
    }


def _cause(claim_id: str) -> dict[str, object]:
    return {"Claim번호": claim_id, "대표원인": "PERIOD_FREQUENCY_GAP", "적용규칙군": "OFFICIAL_PERIOD_NORMALIZATION"}


def test_comparison_counts_complete_progressed_and_unchanged() -> None:
    result = compile_coordinate94_comparison(
        [_before("C1"), _before("C2"), _before("C3")],
        [_after("C1", "완료", "WITHIN_TOLERANCE", "Y"), _after("C2", "후보 의미 비교", "AMBIGUOUS_MARGIN"), _after("C3", "필수 조건 검사", "NO_HARD_GUARD_CANDIDATE")],
        [_cause("C1"), _cause("C2"), _cause("C3")],
        expected_count=3,
    )

    assert result.summary["strict_official_complete_count"] == 1
    assert result.summary["advanced_beyond_original_stage_count"] == 2
    assert result.summary["movement_counts"] == {"공식판정완료": 1, "다음단계진전": 1, "동일단계": 1}


def test_comparison_rejects_missing_after_claim() -> None:
    with pytest.raises(ValueError, match="COVERAGE_MISMATCH"):
        compile_coordinate94_comparison([_before("C1")], [], [_cause("C1")], expected_count=1)
