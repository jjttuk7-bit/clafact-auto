"""Compare the frozen 94-Claim coordinate scope before and after common rules."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Sequence


_STAGES = (
    "사전 구조화",
    "통계 개념 연결",
    "공식 통계표 검색",
    "KOSIS 구조정보 조회",
    "필수 조건 검사",
    "후보 의미 비교",
    "근거 좌표 확정",
    "공식값 조회",
    "결정적 계산",
    "최종 판정",
    "완료",
)


@dataclass(frozen=True, slots=True)
class Coordinate94Comparison:
    rows: tuple[dict[str, object], ...]
    summary: dict[str, object]


def compile_coordinate94_comparison(
    before_rows: Sequence[Mapping[str, object]],
    after_rows: Sequence[Mapping[str, object]],
    classification_rows: Sequence[Mapping[str, object]],
    *,
    expected_count: int = 94,
) -> Coordinate94Comparison:
    before = _index(before_rows, "Claim번호")
    after = _index(after_rows, "Claim번호")
    causes = _index(classification_rows, "Claim번호")
    expected = set(before)
    if len(expected) != expected_count:
        raise ValueError(f"DIRECT_VALUE_94_BEFORE_COUNT:{len(expected)}")
    if set(after) != expected or set(causes) != expected:
        raise ValueError("DIRECT_VALUE_94_COMPARISON_COVERAGE_MISMATCH")

    output: list[dict[str, object]] = []
    for claim_id in sorted(expected):
        old = before[claim_id]
        new = after[claim_id]
        cause = causes[claim_id]
        old_stage = _text(old.get("최종실패단계"))
        new_stage = _text(new.get("최종실패단계"))
        strict = _text(new.get("엄격공식판정완료")) == "Y"
        movement = _movement(old_stage, new_stage, strict)
        output.append({
            "Claim번호": claim_id,
            "원문": _text(new.get("원문") or old.get("원문")),
            "지표": _text(new.get("검색지표")),
            "단위": _text(new.get("단위")),
            "주기": _text(new.get("주기")),
            "지역": _text(new.get("지역")),
            "대표원인": _text(cause.get("대표원인")),
            "적용규칙군": _text(cause.get("적용규칙군")),
            "개선전실패단계": old_stage,
            "개선전사유": _text(old.get("최종사유")),
            "재실행후실패단계": new_stage,
            "재실행후사유": _text(new.get("최종사유")),
            "단계변화": movement,
            "엄격공식판정완료": "Y" if strict else "N",
            "최종판정": _text(new.get("최종판정")),
            "근거좌표수": new.get("근거좌표수", 0),
            "공식값수": new.get("공식값수", 0),
            "공식근거수": new.get("공식근거수", 0),
            "공식근거URL": _text(new.get("공식근거URL")),
            "공식응답해시": _text(new.get("공식응답해시")),
        })

    movement_counts = Counter(_text(row["단계변화"]) for row in output)
    summary = {
        "scope_count": len(output),
        "strict_official_complete_count": sum(row["엄격공식판정완료"] == "Y" for row in output),
        "advanced_beyond_original_stage_count": sum(
            row["단계변화"] in {"공식판정완료", "다음단계진전"} for row in output
        ),
        "movement_counts": dict(sorted(movement_counts.items())),
        "after_reason_counts": dict(sorted(Counter(_text(row["재실행후사유"]) for row in output).items())),
        "after_failure_stage_counts": dict(sorted(Counter(_text(row["재실행후실패단계"]) for row in output).items())),
    }
    return Coordinate94Comparison(tuple(output), summary)


def _movement(old_stage: str, new_stage: str, strict: bool) -> str:
    if strict:
        return "공식판정완료"
    old_rank = _stage_rank(old_stage)
    new_rank = _stage_rank(new_stage)
    if new_rank > old_rank:
        return "다음단계진전"
    if new_rank < old_rank:
        return "후퇴"
    return "동일단계"


def _stage_rank(value: str) -> int:
    try:
        return _STAGES.index(value)
    except ValueError:
        return -1


def _index(rows: Sequence[Mapping[str, object]], key: str) -> dict[str, Mapping[str, object]]:
    indexed: dict[str, Mapping[str, object]] = {}
    for row in rows:
        claim_id = _text(row.get(key))
        if not claim_id or claim_id in indexed:
            raise ValueError("DIRECT_VALUE_94_DUPLICATE_OR_EMPTY_ID")
        indexed[claim_id] = row
    return indexed


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
