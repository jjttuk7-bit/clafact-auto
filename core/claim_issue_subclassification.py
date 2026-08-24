"""Deterministically split broad Claim issue groups into solvable work units."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class IssueSubclass:
    code: str
    description: str
    solution: str


_DONE = IssueSubclass(
    "DONE",
    "최종 판정과 근거 기록이 완료됨",
    "추가 실행 없이 회귀시험에서 결과만 보호",
)

_ISSUES: dict[str, IssueSubclass] = {
    "CONTEXT_RECORD_ASSERTION": IssueSubclass(
        "CONTEXT_RECORD_ASSERTION",
        "직접 수치와 역대 최고·최저 주장이 한 문장에 섞임",
        "직접 수치 주장과 기록 비교 주장을 분리한 뒤 각각 다시 진입",
    ),
    "CONTEXT_MULTI_NUMERIC": IssueSubclass(
        "CONTEXT_MULTI_NUMERIC",
        "연도를 제외한 여러 수치 주장이 한 문장에 섞임",
        "수치 역할을 구분해 자식 Claim으로 분리하고 12개 항목을 다시 작성",
    ),
    "CONTEXT_TIME_RECOVERY": IssueSubclass(
        "CONTEXT_TIME_RECOVERY",
        "검증 기간이 문장만으로 확정되지 않음",
        "기사 작성일과 앞뒤 문장에서 기준 기간을 복구한 뒤 다시 진입",
    ),
    "CONTEXT_COMPARISON_RECOVERY": IssueSubclass(
        "CONTEXT_COMPARISON_RECOVERY",
        "증가·감소의 비교 기준이 빠져 있음",
        "앞뒤 문장에서 비교 대상과 계산 방식을 복구한 뒤 다시 구조화",
    ),
    "CONTEXT_SLOT_COMPLETION": IssueSubclass(
        "CONTEXT_SLOT_COMPLETION",
        "공식 조회에 필요한 12개 항목 일부가 비어 있음",
        "원문과 기사 문맥으로 빈 항목의 근거를 채우고 재진입",
    ),
    "CONTEXT_GENERAL_REPARSE": IssueSubclass(
        "CONTEXT_GENERAL_REPARSE",
        "Claim 구조화 결과가 공식 조회 단계로 넘어가지 못함",
        "원문 수치와 12개 항목의 연결을 다시 검사하고 안전한 Claim만 재진입",
    ),
    "OFFICIAL_CATALOG_SEARCH": IssueSubclass(
        "OFFICIAL_CATALOG_SEARCH",
        "공식 통계표 검색 요청을 완료하지 못함",
        "KOSIS 우선 검색 후 공식 작성기관 보조 경로를 재시도",
    ),
    "OFFICIAL_METADATA_LOOKUP": IssueSubclass(
        "OFFICIAL_METADATA_LOOKUP",
        "찾은 통계표의 항목·기간·분류 구조를 가져오지 못함",
        "공식 표 구조 조회를 재시도하고 대체 공식 메타데이터 경로를 확인",
    ),
    "HARD_GUARD_PERIOD": IssueSubclass(
        "HARD_GUARD_PERIOD",
        "기사 기간·주기와 공식 표 기간이 연결되지 않음",
        "연·분기·월 표현과 제공 시작·종료 기간을 표준화해 다시 비교",
    ),
    "HARD_GUARD_UNIT_VALUE": IssueSubclass(
        "HARD_GUARD_UNIT_VALUE",
        "기사 수치·단위와 공식 표 단위가 연결되지 않음",
        "단위 환산 없이 같은 단위만 통과하도록 단위 동의어와 경계를 보강",
    ),
    "HARD_GUARD_DIMENSION": IssueSubclass(
        "HARD_GUARD_DIMENSION",
        "지역·대상·분류 같은 필수 조건이 연결되지 않음",
        "공식 표의 지역·대상·분류 이름과 기사 표현의 안전한 동의어를 보강",
    ),
    "HARD_GUARD_ALIAS": IssueSubclass(
        "HARD_GUARD_ALIAS",
        "필수 조건을 만족하는 후보가 남지 않음",
        "탈락한 조건을 기록하고 반복되는 공식 명칭 차이만 보강",
    ),
    "COORDINATE_PERIOD": IssueSubclass(
        "COORDINATE_PERIOD",
        "통계표 안에서 정확한 기간 좌표를 확정하지 못함",
        "공식 기간 코드와 기사 기준 기간을 연결",
    ),
    "COORDINATE_UNIT_VALUE": IssueSubclass(
        "COORDINATE_UNIT_VALUE",
        "통계표 안에서 수치 항목과 단위 좌표를 확정하지 못함",
        "공식 항목·단위 구조를 읽어 정확한 셀 후보를 다시 생성",
    ),
    "COORDINATE_DIMENSION": IssueSubclass(
        "COORDINATE_DIMENSION",
        "통계표 안에서 지역·대상·분류 좌표를 확정하지 못함",
        "전체·전국·계 등 기사 표현을 공식 차원 코드와 안전하게 연결",
    ),
    "COORDINATE_GENERAL": IssueSubclass(
        "COORDINATE_GENERAL",
        "통계표는 찾았지만 공식값 셀을 하나로 확정하지 못함",
        "공식 표 구조에서 항목·지역·기간·단위 후보와 탈락 이유를 다시 기록",
    ),
    "SEMANTIC_CONCEPT_NOT_FOUND": IssueSubclass(
        "SEMANTIC_CONCEPT_NOT_FOUND",
        "기사 지표에 맞는 표준 통계 개념을 찾지 못함",
        "반복 분야의 공식 개념과 기사 표현을 의미 표준에 추가",
    ),
    "SEMANTIC_LOW_SCORE": IssueSubclass(
        "SEMANTIC_LOW_SCORE",
        "후보 개념의 의미 일치 점수가 기준보다 낮음",
        "지표 정의·대상·단위 설명을 보강하고 같은 개념 후보만 다시 비교",
    ),
    "SEMANTIC_AMBIGUOUS": IssueSubclass(
        "SEMANTIC_AMBIGUOUS",
        "서로 비슷한 공식 개념 후보를 안전하게 구분하지 못함",
        "후보 차이를 기록하고 구분 조건이 없으면 사람 검토로 유지",
    ),
    "SEMANTIC_GENERAL": IssueSubclass(
        "SEMANTIC_GENERAL",
        "표준 통계 개념 연결 단계에서 중단됨",
        "기사 지표 정의와 공식 개념 정의를 다시 비교",
    ),
    "VALUE_FETCH_FAILED": IssueSubclass(
        "VALUE_FETCH_FAILED",
        "확정 좌표의 공식값 조회를 완료하지 못함",
        "요청 좌표와 응답 오류를 기록하고 공식값 API를 제한 재시도",
    ),
    "VALUE_ARTICLE_TIME_UNAVAILABLE": IssueSubclass(
        "VALUE_ARTICLE_TIME_UNAVAILABLE",
        "기사 작성 당시 공개된 공식값을 확인하지 못함",
        "공식 보도자료와 첨부표에서 기사 시점 값을 복구하고 못 찾으면 보류 유지",
    ),
    "VALUE_PUBLICATION_LOOKUP": IssueSubclass(
        "VALUE_PUBLICATION_LOOKUP",
        "대상 기간의 공식 발표 자료를 확인하지 못함",
        "KOSIS 통계설명과 작성기관 발표 페이지를 기간별로 다시 확인",
    ),
    "VALUE_GENERAL": IssueSubclass(
        "VALUE_GENERAL",
        "공식값 또는 발표정보 단계에서 중단됨",
        "값 조회와 발표정보 조회를 분리해 실제 실패 경로를 다시 기록",
    ),
    "CALCULATION_RECORD_HISTORY": IssueSubclass(
        "CALCULATION_RECORD_HISTORY",
        "역대 최고·최저 비교에 필요한 전체 기간 값 범위를 만들지 못함",
        "공식 제공 시작일부터 기사 기간까지 같은 주기의 전체 이력을 조회해 비교",
    ),
    "CALCULATION_CHANGE_RATE": IssueSubclass(
        "CALCULATION_CHANGE_RATE",
        "증감률 계산에 필요한 현재값과 기준값을 확정하지 못함",
        "현재·비교 기간의 공식값 두 개를 확정하고 파이썬 증감률 계산을 실행",
    ),
    "CALCULATION_DIFFERENCE": IssueSubclass(
        "CALCULATION_DIFFERENCE",
        "증가·감소량 계산에 필요한 두 공식값을 확정하지 못함",
        "현재값과 기준값을 같은 단위로 조회해 파이썬 차이 계산을 실행",
    ),
    "CALCULATION_COMPOSITION": IssueSubclass(
        "CALCULATION_COMPOSITION",
        "비중·구성비 계산의 분자와 분모를 확정하지 못함",
        "분자·분모 공식 좌표를 분리해 파이썬 비율 계산을 실행",
    ),
    "CALCULATION_RANK": IssueSubclass(
        "CALCULATION_RANK",
        "순위 계산에 필요한 비교 집단 전체를 확정하지 못함",
        "같은 기준의 비교 집단 전체 공식값을 조회해 파이썬 순위를 계산",
    ),
    "CALCULATION_GENERAL": IssueSubclass(
        "CALCULATION_GENERAL",
        "공식값은 있으나 필요한 계산 입력과 식을 확정하지 못함",
        "Claim 계산 유형과 필요한 공식값 좌표를 명시한 계산 계획을 작성",
    ),
}

_REASON_GROUP = {
    "CONTEXT_REQUIRED": "CONTEXT",
    "MULTI_CLAIM_SPLIT_REQUIRED": "CONTEXT",
    "STRUCTURAL_HOLD": "CONTEXT",
    "KOSIS_CATALOG_UNAVAILABLE": "OFFICIAL_PATH",
    "KOSIS_METADATA_UNAVAILABLE": "OFFICIAL_PATH",
    "NO_HARD_GUARD_CANDIDATE": "HARD_GUARD",
    "NO_EVIDENCE_COORDINATE_CANDIDATE": "COORDINATE",
    "CONCEPT_NOT_FOUND": "SEMANTIC",
    "LOW_SEMANTIC_SCORE": "SEMANTIC",
    "AMBIGUOUS_MARGIN": "SEMANTIC",
    "FETCH_FAILED": "VALUE_PUBLICATION",
    "AS_OF_UNAVAILABLE": "VALUE_PUBLICATION",
    "PUBLICATION_FETCH_FAILED": "VALUE_PUBLICATION",
    "CALCULATION_EVIDENCE_PLAN_UNRESOLVED": "CALCULATION",
    "CALCULATION_FAILED": "CALCULATION",
}

_RECORD_RE = re.compile(r"역대|사상|최대|최고|최저|최소")
_CHANGE_RE = re.compile(r"증가|감소|늘(?:었|어|고|어난)|줄(?:었|어|고|어든)|상승|하락|증감|대비")
_RATE_RE = re.compile(r"%|퍼센트|증가율|감소율|증감률")
_COMPOSITION_RE = re.compile(r"비중|구성비|점유율")
_RANK_RE = re.compile(r"순위|위로|위였다|위를 기록")
_KOREAN_NUMBER = (
    r"[+-]?\d[\d,]*(?:\.\d+)?(?:\s*(?:조|억|만|천|백)\s*\d[\d,]*(?:\.\d+)?)*(?:\s*(?:조|억|만|천|백))?"
)
_NUMBER_RE = re.compile(rf"(?<![A-Za-z0-9_]){_KOREAN_NUMBER}(?:\s*[~～]\s*{_KOREAN_NUMBER})?")
_MISSING_RE = re.compile(r"([a-z_]+)=MISSING")


def classify_issue_subclass(row: Mapping[str, str]) -> IssueSubclass:
    if str(row.get("남은작업") or "") == "완료":
        return _DONE

    reason = str(row.get("최신결과사유") or row.get("현재사유") or "")
    stage = str(row.get("최신결과단계") or row.get("현재중단단계") or "")
    group = _effective_group(str(row.get("현재문제묶음") or ""), reason, stage)
    source = str(row.get("원문") or "")
    missing = set(_MISSING_RE.findall(str(row.get("12개항목상태") or "")))

    if group == "CONTEXT":
        if _RECORD_RE.search(source):
            return _ISSUES["CONTEXT_RECORD_ASSERTION"]
        if _non_year_number_count(source) >= 2:
            return _ISSUES["CONTEXT_MULTI_NUMERIC"]
        if "time" in missing or "frequency" in missing:
            return _ISSUES["CONTEXT_TIME_RECOVERY"]
        if "comparison" in missing and _CHANGE_RE.search(source):
            return _ISSUES["CONTEXT_COMPARISON_RECOVERY"]
        if missing:
            return _ISSUES["CONTEXT_SLOT_COMPLETION"]
        return _ISSUES["CONTEXT_GENERAL_REPARSE"]
    if group == "OFFICIAL_PATH":
        if "KOSIS_METADATA_UNAVAILABLE" in reason or "KOSIS_METADATA" in stage:
            return _ISSUES["OFFICIAL_METADATA_LOOKUP"]
        return _ISSUES["OFFICIAL_CATALOG_SEARCH"]
    if group == "HARD_GUARD":
        return _slot_specific("HARD_GUARD", missing)
    if group == "COORDINATE":
        return _slot_specific("COORDINATE", missing)
    if group == "SEMANTIC":
        if "CONCEPT_NOT_FOUND" in reason:
            return _ISSUES["SEMANTIC_CONCEPT_NOT_FOUND"]
        if "LOW_SEMANTIC_SCORE" in reason:
            return _ISSUES["SEMANTIC_LOW_SCORE"]
        if "AMBIGUOUS_MARGIN" in reason:
            return _ISSUES["SEMANTIC_AMBIGUOUS"]
        return _ISSUES["SEMANTIC_GENERAL"]
    if group == "VALUE_PUBLICATION":
        if "AS_OF_UNAVAILABLE" in reason:
            return _ISSUES["VALUE_ARTICLE_TIME_UNAVAILABLE"]
        if "PUBLICATION_FETCH_FAILED" in reason:
            return _ISSUES["VALUE_PUBLICATION_LOOKUP"]
        if "FETCH_FAILED" in reason:
            return _ISSUES["VALUE_FETCH_FAILED"]
        return _ISSUES["VALUE_GENERAL"]
    if group == "CALCULATION":
        if _RECORD_RE.search(source):
            return _ISSUES["CALCULATION_RECORD_HISTORY"]
        if _RATE_RE.search(source):
            return _ISSUES["CALCULATION_CHANGE_RATE"]
        if _COMPOSITION_RE.search(source):
            return _ISSUES["CALCULATION_COMPOSITION"]
        if _RANK_RE.search(source):
            return _ISSUES["CALCULATION_RANK"]
        if _CHANGE_RE.search(source):
            return _ISSUES["CALCULATION_DIFFERENCE"]
        return _ISSUES["CALCULATION_GENERAL"]
    return IssueSubclass(
        f"{group or 'UNCLASSIFIED'}_GENERAL",
        "현재 기록만으로 더 작은 문제 유형을 확정하지 못함",
        "최신 중단 단계와 원문 근거를 다시 확인해 분류",
    )


def annotate_issue_subclasses(
    rows: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    annotated: list[dict[str, str]] = []
    for row in rows:
        result = classify_issue_subclass(row)
        copied = dict(row)
        copied.update({
            "세부문제유형": result.code,
            "세부문제설명": result.description,
            "해결방법": result.solution,
            "처리우선순위": "",
            "대표실행묶음": "",
        })
        annotated.append(copied)

    counts = Counter(
        row["세부문제유형"]
        for row in annotated
        if row["세부문제유형"] != "DONE"
    )
    ordered = sorted(counts, key=lambda code: (-counts[code], code))
    priorities = {code: str(index) for index, code in enumerate(ordered, start=1)}
    by_subtype: dict[str, list[dict[str, str]]] = {}
    for row in annotated:
        code = row["세부문제유형"]
        if code == "DONE":
            continue
        row["처리우선순위"] = priorities[code]
        by_subtype.setdefault(code, []).append(row)
    for code, candidates in by_subtype.items():
        batch_id = f"{code}-001"
        for row in sorted(candidates, key=lambda item: item.get("Claim번호", ""))[:20]:
            row["대표실행묶음"] = batch_id
    return annotated


def summarize_issue_subclasses(rows: Sequence[Mapping[str, str]]) -> dict[str, object]:
    remaining = [row for row in rows if str(row.get("세부문제유형") or "") != "DONE"]
    counts = Counter(str(row.get("세부문제유형") or "") for row in remaining)
    first_priority = min(
        (int(str(row.get("처리우선순위") or "0")) for row in remaining),
        default=0,
    )
    first_rows = sorted(
        (
            row for row in remaining
            if int(str(row.get("처리우선순위") or "0")) == first_priority
            and row.get("대표실행묶음")
        ),
        key=lambda row: str(row.get("Claim번호") or ""),
    )
    return {
        "subclassified_remaining_count": len(remaining),
        "remaining_by_subtype": dict(sorted(counts.items())),
        "first_execution_batch": {
            "batch_id": str(first_rows[0].get("대표실행묶음") or "") if first_rows else "",
            "subtype": str(first_rows[0].get("세부문제유형") or "") if first_rows else "",
            "count": len(first_rows),
            "claim_ids": [str(row.get("Claim번호") or "") for row in first_rows],
        },
    }


def _effective_group(group: str, reason: str, stage: str) -> str:
    for token in reason.split("|"):
        if token in _REASON_GROUP:
            return _REASON_GROUP[token]
    if stage == "KOSIS_METADATA":
        return "OFFICIAL_PATH"
    return group


def _slot_specific(prefix: str, missing: set[str]) -> IssueSubclass:
    if missing & {"time", "frequency"}:
        return _ISSUES[f"{prefix}_PERIOD"]
    if missing & {"value", "unit"}:
        return _ISSUES[f"{prefix}_UNIT_VALUE"]
    if missing & {"dimension", "condition", "region", "population"}:
        return _ISSUES[f"{prefix}_DIMENSION"]
    suffix = "ALIAS" if prefix == "HARD_GUARD" else "GENERAL"
    return _ISSUES[f"{prefix}_{suffix}"]


def _non_year_number_count(source: str) -> int:
    count = 0
    previous_value_end: int | None = None
    for match in _NUMBER_RE.finditer(source):
        suffix = source[match.end():].lstrip()
        if suffix.startswith(("년", "월", "일", "분기", "위", "인당")):
            continue
        if previous_value_end is not None:
            bridge = source[previous_value_end:match.start()]
            if re.fullmatch(r"\s*%?\s*(?:내지|에서|부터|~|～)\s*", bridge):
                previous_value_end = match.end()
                continue
        raw = match.group(0).replace(",", "")
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", raw):
            value = float(raw)
            if value.is_integer() and 1900 <= value <= 2099:
                continue
        count += 1
        previous_value_end = match.end()
    return count

