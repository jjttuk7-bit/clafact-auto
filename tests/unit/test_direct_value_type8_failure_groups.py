from core.direct_value_type8_failure_groups import classify_type8_result


def test_type8_failure_groups_are_mutually_exclusive() -> None:
    assert classify_type8_result({"8번엄격공식판정완료": "Y"})[0] == "공식 판정 완료"
    assert classify_type8_result({"8번최종상태": "PRE_VERIFICATION"})[0] == "Claim 구조 보완 필요"
    assert classify_type8_result({"8번최종상태": "HUMAN_REVIEW"})[0] == "Claim 의미·역할 검토 필요"
    assert classify_type8_result({"8번최종사유": "NO_HARD_GUARD_CANDIDATE"})[0] == "공식표 필수조건 불일치"
    assert classify_type8_result({"8번최종사유": "NO_EVIDENCE_COORDINATE_CANDIDATE"})[0] == "공식 좌표 미확정"
    assert classify_type8_result({"8번최종사유": "AS_OF_UNAVAILABLE"})[0] == "기사 작성일 기준 공표 확인 실패"
    assert classify_type8_result({"8번최종사유": "FETCH_FAILED"})[0] == "공식 API 검색·값 조회 실패"
    assert classify_type8_result({"8번최종사유": "AMBIGUOUS_MARGIN"})[0] == "공식 후보 의미 불확실"
