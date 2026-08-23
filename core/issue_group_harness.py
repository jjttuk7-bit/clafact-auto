"""Bounded issue-group control plane for Registry improvement runs."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class IssueGroup(StrEnum):
    CONTEXT = "CONTEXT"
    OFFICIAL_PATH = "OFFICIAL_PATH"
    HARD_GUARD = "HARD_GUARD"
    COORDINATE = "COORDINATE"
    SEMANTIC = "SEMANTIC"
    CALCULATION = "CALCULATION"
    VALUE_PUBLICATION = "VALUE_PUBLICATION"
    REGRESSION = "REGRESSION"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True, slots=True)
class ClaimIssueRecord:
    article_id: str
    sentence_id: str
    parent_claim_id: str
    claim_id: str
    source_sentence: str
    current_status: str
    current_reason: str | None
    current_stop_stage: str | None
    primary_group: IssueGroup
    secondary_issues: tuple[str, ...] = ()


_REASON_GROUP: dict[str, IssueGroup] = {
    "CONTEXT_REQUIRED": IssueGroup.CONTEXT,
    "MULTI_CLAIM_SPLIT_REQUIRED": IssueGroup.CONTEXT,
    "STRUCTURAL_HOLD": IssueGroup.CONTEXT,
    "KOSIS_CATALOG_UNAVAILABLE": IssueGroup.OFFICIAL_PATH,
    "KOSIS_METADATA_UNAVAILABLE": IssueGroup.OFFICIAL_PATH,
    "NO_HARD_GUARD_CANDIDATE": IssueGroup.HARD_GUARD,
    "NO_EVIDENCE_COORDINATE_CANDIDATE": IssueGroup.COORDINATE,
    "LOW_SEMANTIC_SCORE": IssueGroup.SEMANTIC,
    "AMBIGUOUS_MARGIN": IssueGroup.SEMANTIC,
    "CONCEPT_NOT_FOUND": IssueGroup.SEMANTIC,
    "CALCULATION_EVIDENCE_PLAN_UNRESOLVED": IssueGroup.CALCULATION,
    "CALCULATION_FAILED": IssueGroup.CALCULATION,
    "FETCH_FAILED": IssueGroup.VALUE_PUBLICATION,
    "AS_OF_UNAVAILABLE": IssueGroup.VALUE_PUBLICATION,
    "PUBLICATION_FETCH_FAILED": IssueGroup.VALUE_PUBLICATION,
}

_REASON_STAGE: dict[str, str] = {
    "CONTEXT_REQUIRED": "CLAIM_PARSE",
    "MULTI_CLAIM_SPLIT_REQUIRED": "CLAIM_SPLIT",
    "STRUCTURAL_HOLD": "CLAIM_PARSE",
    "KOSIS_CATALOG_UNAVAILABLE": "CATALOG_SEARCH",
    "KOSIS_METADATA_UNAVAILABLE": "KOSIS_METADATA",
    "NO_HARD_GUARD_CANDIDATE": "HARD_GUARD",
    "NO_EVIDENCE_COORDINATE_CANDIDATE": "EVIDENCE_CELL",
    "LOW_SEMANTIC_SCORE": "SEMANTIC_MATCH",
    "AMBIGUOUS_MARGIN": "SEMANTIC_MATCH",
    "CONCEPT_NOT_FOUND": "SEMANTIC_MAPPING",
    "CALCULATION_EVIDENCE_PLAN_UNRESOLVED": "CALCULATION",
    "CALCULATION_FAILED": "CALCULATION",
    "FETCH_FAILED": "OFFICIAL_VALUE_FETCH",
    "AS_OF_UNAVAILABLE": "OFFICIAL_VALUE_FETCH",
    "PUBLICATION_FETCH_FAILED": "OFFICIAL_VALUE_FETCH",
}

_STAGE_ORDER = {
    name: index
    for index, name in enumerate(
        (
            "PREPROCESS",
            "SENTENCE_SPLIT",
            "CLAIM_CANDIDATE_SELECTION",
            "CLAIM_SPLIT",
            "CLAIM_PARSE",
            "SEMANTIC_MAPPING",
            "CATALOG_SEARCH",
            "KOSIS_METADATA",
            "HARD_GUARD",
            "SEMANTIC_MATCH",
            "EVIDENCE_CELL",
            "OFFICIAL_VALUE_FETCH",
            "CALCULATION",
            "VERDICT",
        )
    )
}


def classify_claim(row: dict[str, Any]) -> ClaimIssueRecord:
    """Assign one primary issue from the earliest observed failing stage."""

    status, terminal_reason = _terminal(row)
    failures = _observed_failures(row)
    if status == "AUTO":
        group = IssueGroup.REGRESSION
        stop_stage = "VERDICT"
        secondary: tuple[str, ...] = ()
    elif failures:
        ordered = sorted(
            enumerate(failures),
            key=lambda item: (_STAGE_ORDER.get(item[1][0], 10_000), item[0]),
        )
        _, (stop_stage, primary_reason) = ordered[0]
        terminal_reason = primary_reason
        group = _REASON_GROUP.get(primary_reason, IssueGroup.UNCLASSIFIED)
        secondary = tuple(
            f"{stage}:{reason}" for _, (stage, reason) in ordered[1:]
        )
    else:
        group = _REASON_GROUP.get(terminal_reason or "", IssueGroup.UNCLASSIFIED)
        stop_stage = _REASON_STAGE.get(terminal_reason or "")
        secondary = ()

    return ClaimIssueRecord(
        article_id=str(row.get("article_id") or ""),
        sentence_id=str(row.get("sentence_id") or ""),
        parent_claim_id=str(row.get("parent_claim_id") or ""),
        claim_id=str(row.get("claim_id") or ""),
        source_sentence=str(row.get("source_sentence") or ""),
        current_status=status,
        current_reason=terminal_reason,
        current_stop_stage=stop_stage,
        primary_group=group,
        secondary_issues=secondary,
    )


def _terminal(row: dict[str, Any]) -> tuple[str, str | None]:
    resolution = row.get("official_resolution")
    verdict = resolution.get("verdict") if isinstance(resolution, dict) else None
    if isinstance(verdict, dict):
        return (
            str(verdict.get("route_status") or row.get("terminal_status") or "HOLD"),
            _text(verdict.get("reason_code") or row.get("reason_code")),
        )
    return (
        str(row.get("terminal_status") or "HOLD"),
        _text(row.get("reason_code") or row.get("admission_route")),
    )


def _observed_failures(row: dict[str, Any]) -> list[tuple[str, str]]:
    resolution = row.get("official_resolution")
    verdict = resolution.get("verdict") if isinstance(resolution, dict) else None
    trace = verdict.get("execution_trace") if isinstance(verdict, dict) else None
    events = trace.get("events") if isinstance(trace, dict) else None
    failures: list[tuple[str, str]] = []
    for event in events or []:
        if not isinstance(event, dict) or event.get("status") == "PASS":
            continue
        stage = _text(event.get("stage"))
        reason = _text(event.get("reason_code"))
        if stage and reason:
            failures.append((stage, reason))
    return failures


def _text(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None


_LEDGER_HEADERS = (
    "기사번호",
    "문장번호",
    "부모Claim번호",
    "Claim번호",
    "원문",
    "현재상태",
    "현재중단단계",
    "현재사유",
    "대표문제",
    "보조문제",
    "다음실행단계",
    "개선전상태",
    "개선전사유",
    "개선후상태",
    "개선후사유",
    "공식통계표",
    "공식값출처",
    "실행횟수",
    "코드버전",
    "데이터버전",
    "기록시각",
)

_NEXT_STAGE = {
    IssueGroup.CONTEXT: "CLAIM_SPLIT~CLAIM_PARSE",
    IssueGroup.OFFICIAL_PATH: "SEMANTIC_MAPPING~KOSIS_METADATA",
    IssueGroup.HARD_GUARD: "HARD_GUARD",
    IssueGroup.COORDINATE: "EVIDENCE_CELL",
    IssueGroup.SEMANTIC: "SEMANTIC_MAPPING~SEMANTIC_MATCH",
    IssueGroup.CALCULATION: "CALCULATION",
    IssueGroup.VALUE_PUBLICATION: "OFFICIAL_VALUE_FETCH~VERDICT",
    IssueGroup.REGRESSION: "전체경로 회귀검사",
    IssueGroup.UNCLASSIFIED: "실행금지: 먼저 분류",
}


def build_issue_registry(rows: list[dict[str, Any]]) -> list[ClaimIssueRecord]:
    """Classify rows while rejecting identities that cannot be audited."""

    records: list[ClaimIssueRecord] = []
    identities: set[tuple[str, str, str, str]] = set()
    for row in rows:
        record = classify_claim(row)
        identity = (
            record.article_id,
            record.sentence_id,
            record.parent_claim_id,
            record.claim_id,
        )
        if not all(identity):
            raise ValueError("MISSING_CLAIM_IDENTITY")
        if identity in identities:
            raise ValueError(f"DUPLICATE_CLAIM_IDENTITY:{'|'.join(identity)}")
        identities.add(identity)
        records.append(record)
    return sorted(
        records,
        key=lambda item: (
            item.primary_group.value,
            item.article_id,
            item.sentence_id,
            item.parent_claim_id,
            item.claim_id,
        ),
    )


def write_issue_ledgers(
    records: list[ClaimIssueRecord],
    output_dir: Path,
) -> dict[IssueGroup, dict[str, int]]:
    """Write one reconciled master ledger and one ledger per primary group."""

    output_dir.mkdir(parents=True, exist_ok=True)
    group_dir = output_dir / "groups"
    group_dir.mkdir(parents=True, exist_ok=True)
    rows = [_ledger_row(record) for record in records]
    _write_csv_atomic(output_dir / "claim_issue_master.csv", _LEDGER_HEADERS, rows)

    counts = Counter(record.primary_group for record in records)
    summary: dict[IssueGroup, dict[str, int]] = {}
    for group in IssueGroup:
        group_rows = [
            row for record, row in zip(records, rows, strict=True)
            if record.primary_group is group
        ]
        if group_rows:
            _write_csv_atomic(group_dir / f"{group.value}.csv", _LEDGER_HEADERS, group_rows)
        summary[group] = {
            "전체수": counts[group],
            "시도수": 0,
            "개선수": 0,
            "남은수": counts[group],
        }

    summary_headers = ("문제코드", "전체수", "시도수", "개선수", "남은수", "완료여부")
    summary_rows = [
        {
            "문제코드": group.value,
            **values,
            "완료여부": "아니오" if values["남은수"] else "예",
        }
        for group, values in summary.items()
    ]
    _write_csv_atomic(output_dir / "group_summary.csv", summary_headers, summary_rows)
    if sum(values["전체수"] for values in summary.values()) != len(records):
        raise ValueError("GROUP_TOTAL_MISMATCH")
    return summary


def _ledger_row(record: ClaimIssueRecord) -> dict[str, object]:
    return {
        "기사번호": record.article_id,
        "문장번호": record.sentence_id,
        "부모Claim번호": record.parent_claim_id,
        "Claim번호": record.claim_id,
        "원문": record.source_sentence,
        "현재상태": record.current_status,
        "현재중단단계": record.current_stop_stage or "",
        "현재사유": record.current_reason or "",
        "대표문제": record.primary_group.value,
        "보조문제": " | ".join(record.secondary_issues),
        "다음실행단계": _NEXT_STAGE[record.primary_group],
        "개선전상태": record.current_status,
        "개선전사유": record.current_reason or "",
        "개선후상태": "",
        "개선후사유": "",
        "공식통계표": "",
        "공식값출처": "",
        "실행횟수": 0,
        "코드버전": "",
        "데이터버전": "",
        "기록시각": "",
    }


def _write_csv_atomic(
    path: Path,
    headers: tuple[str, ...],
    rows: list[dict[str, object]],
) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)
