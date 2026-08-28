from __future__ import annotations

from typing import Mapping


def classify_type8_result(row: Mapping[str, object]) -> tuple[str, str]:
    if str(row.get("8번엄격공식판정완료") or "").strip().upper() == "Y":
        return "공식 판정 완료", "추가 조치 없음"

    status = str(row.get("8번최종상태") or "").strip().upper()
    reason = str(row.get("8번최종사유") or "").strip().upper()
    if status == "PRE_VERIFICATION":
        return "Claim 구조 보완 필요", "원문에서 지표·검증값·시점·주기를 복구한 뒤 같은 파이프라인에 재투입"
    if status == "HUMAN_REVIEW":
        return "Claim 의미·역할 검토 필요", "직접값 여부와 수치 역할을 확정해 이동·제외·재투입"
    if reason == "NO_HARD_GUARD_CANDIDATE":
        return "공식표 필수조건 불일치", "표·항목의 단위·주기·지역·대상 조건을 Claim과 일치시키는 공통 규칙 보강"
    if reason == "NO_EVIDENCE_COORDINATE_CANDIDATE":
        return "공식 좌표 미확정", "선택된 표의 항목·기간·지역·분류 코드를 메타데이터로 확정"
    if reason in {"AS_OF_UNAVAILABLE", "PUBLICATION_FETCH_FAILED"}:
        return "기사 작성일 기준 공표 확인 실패", "해당 기준시점의 공식 공표일·보도자료 경로를 확인"
    if reason in {"KOSIS_CATALOG_UNAVAILABLE", "FETCH_FAILED"}:
        return "공식 API 검색·값 조회 실패", "공식 API 재시도 후 작성기관 보조 경로로 전환"
    if reason in {"AMBIGUOUS_MARGIN", "LOW_SEMANTIC_SCORE"}:
        return "공식 후보 의미 불확실", "지표·대상·차원 동의어를 보강하고 모호한 후보는 사람 검토"
    return "기타 미완료", "원장에 기록된 최종 사유와 실패 단계에서 재처리"
