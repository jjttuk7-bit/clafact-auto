"""Bounded issue-group control plane for Registry improvement runs."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
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
    domain: str = ""
    slot_summary: str = ""
    eligible_for_official_search: bool = False
    catalog_attempted: int = 0
    metadata_item_attempted: int = 0
    metadata_period_attempted: int = 0


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

    details = _classification_details(row)
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
        domain=details["domain"],
        slot_summary=details["slot_summary"],
        eligible_for_official_search=details["eligible"],
        catalog_attempted=details["catalog_attempted"],
        metadata_item_attempted=details["metadata_item_attempted"],
        metadata_period_attempted=details["metadata_period_attempted"],
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


def _classification_details(row: dict[str, Any]) -> dict[str, Any]:
    claim = row.get("claim")
    domain = str(
        row.get("domain")
        or (claim.get("domain") if isinstance(claim, dict) else "")
        or ""
    )
    slot_audit = row.get("slot_audit")
    entries = slot_audit.get("entries") if isinstance(slot_audit, dict) else []
    slot_parts = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        slot = str(entry.get("slot") or "")
        status = str(entry.get("status") or "")
        if slot and status:
            slot_parts.append(f"{slot}={status}")
    resolution = row.get("official_resolution")
    diagnostics = (
        resolution.get("catalog_diagnostics")
        if isinstance(resolution, dict)
        else None
    )
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    return {
        "domain": domain,
        "slot_summary": " | ".join(slot_parts),
        "eligible": bool(
            slot_audit.get("eligible_for_official_search")
            if isinstance(slot_audit, dict)
            else False
        ),
        "catalog_attempted": int(diagnostics.get("attempted_queries") or 0),
        "metadata_item_attempted": int(
            diagnostics.get("metadata_itm_attempted") or 0
        ),
        "metadata_period_attempted": int(
            diagnostics.get("metadata_prd_attempted") or 0
        ),
    }


_LEDGER_HEADERS = (
    "기사번호",
    "문장번호",
    "부모Claim번호",
    "Claim번호",
    "원문",
    "분야",
    "12개항목상태",
    "12개항목공식조회가능",
    "통계표검색시도",
    "항목정보조회시도",
    "기간정보조회시도",
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
    "개선판정",
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
        "분야": record.domain,
        "12개항목상태": record.slot_summary,
        "12개항목공식조회가능": "예" if record.eligible_for_official_search else "아니오",
        "통계표검색시도": record.catalog_attempted,
        "항목정보조회시도": record.metadata_item_attempted,
        "기간정보조회시도": record.metadata_period_attempted,
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
        "개선판정": "",
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


@dataclass(frozen=True, slots=True)
class GroupPolicy:
    group: IssueGroup
    allowed_stages: tuple[str, ...]


_GROUP_POLICIES = {
    IssueGroup.CONTEXT: GroupPolicy(
        IssueGroup.CONTEXT,
        ("CLAIM_SPLIT", "CLAIM_PARSE"),
    ),
    IssueGroup.OFFICIAL_PATH: GroupPolicy(
        IssueGroup.OFFICIAL_PATH,
        ("SEMANTIC_MAPPING", "CATALOG_SEARCH", "KOSIS_METADATA"),
    ),
    IssueGroup.HARD_GUARD: GroupPolicy(
        IssueGroup.HARD_GUARD,
        ("HARD_GUARD",),
    ),
    IssueGroup.COORDINATE: GroupPolicy(
        IssueGroup.COORDINATE,
        ("EVIDENCE_CELL",),
    ),
    IssueGroup.SEMANTIC: GroupPolicy(
        IssueGroup.SEMANTIC,
        ("SEMANTIC_MAPPING", "SEMANTIC_MATCH"),
    ),
    IssueGroup.CALCULATION: GroupPolicy(
        IssueGroup.CALCULATION,
        ("CALCULATION",),
    ),
    IssueGroup.VALUE_PUBLICATION: GroupPolicy(
        IssueGroup.VALUE_PUBLICATION,
        ("OFFICIAL_VALUE_FETCH", "VERDICT"),
    ),
    IssueGroup.REGRESSION: GroupPolicy(
        IssueGroup.REGRESSION,
        tuple(_STAGE_ORDER),
    ),
}


def select_group_slice(
    records: list[ClaimIssueRecord],
    group: IssueGroup | None,
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[ClaimIssueRecord]:
    """Select a stable bounded slice from one explicit issue group."""

    if group is None:
        raise ValueError("GROUP_REQUIRED")
    if group is IssueGroup.UNCLASSIFIED:
        raise ValueError("UNCLASSIFIED_GROUP_CANNOT_RUN")
    if not 1 <= limit <= 50:
        raise ValueError("LIMIT_MUST_BE_BETWEEN_1_AND_50")
    if offset < 0:
        raise ValueError("OFFSET_MUST_BE_NON_NEGATIVE")
    matching = sorted(
        (record for record in records if record.primary_group is group),
        key=lambda item: (
            item.article_id,
            item.sentence_id,
            item.parent_claim_id,
            item.claim_id,
        ),
    )
    return matching[offset : offset + limit]


def run_group_slice(
    records: list[ClaimIssueRecord],
    group: IssueGroup | None,
    executor: Any,
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Run one bounded group and reject traces outside its stage policy."""

    selected = select_group_slice(records, group, limit=limit, offset=offset)
    assert group is not None
    policy = _GROUP_POLICIES[group]
    results: list[dict[str, Any]] = []
    allowed = set(policy.allowed_stages)
    for record in selected:
        result = executor(record, policy.allowed_stages)
        if not isinstance(result, dict):
            raise TypeError("GROUP_EXECUTOR_MUST_RETURN_DICT")
        for stage in result.get("executed_stages") or []:
            if stage not in allowed:
                raise ValueError(f"STAGE_OUT_OF_GROUP_POLICY:{stage}")
        results.append(result)
    return results


@dataclass(frozen=True, slots=True)
class RunComparison:
    claim_id: str
    before_status: str
    before_reason: str | None
    before_stage: str | None
    after_status: str
    after_reason: str | None
    after_stage: str | None
    outcome: str
    official_evidence: bool
    table_id: str | None = None
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class GroupGateResult:
    group: IssueGroup
    passed: bool
    reasons: tuple[str, ...]
    code_version: str
    data_version: str
    evaluated_at: str


_OFFICIAL_GROUPS = {
    IssueGroup.OFFICIAL_PATH,
    IssueGroup.HARD_GUARD,
    IssueGroup.COORDINATE,
    IssueGroup.SEMANTIC,
    IssueGroup.CALCULATION,
    IssueGroup.VALUE_PUBLICATION,
    IssueGroup.REGRESSION,
}

_RUN_HEADERS = (
    "실행번호",
    "Claim번호",
    "대표문제",
    "개선전상태",
    "개선전단계",
    "개선전사유",
    "개선후상태",
    "개선후단계",
    "개선후사유",
    "개선판정",
    "공식근거확인",
    "공식통계표",
    "공식값출처",
    "코드버전",
    "데이터버전",
    "기록시각",
)


def compare_result(
    before: ClaimIssueRecord,
    after: dict[str, Any],
) -> RunComparison:
    """Compare pipeline progress without treating a changed reason as success."""

    claim_id = str(after.get("claim_id") or "")
    if claim_id != before.claim_id:
        raise ValueError(f"RESULT_CLAIM_ID_MISMATCH:{before.claim_id}:{claim_id}")
    after_status = str(after.get("status") or after.get("terminal_status") or "")
    after_reason = _text(after.get("reason_code"))
    after_stage = _text(after.get("stop_stage"))
    if not after_status or not after_stage:
        raise ValueError(f"INCOMPLETE_AFTER_RESULT:{claim_id}")
    if after_status == "AUTO":
        outcome = "RESOLVED"
    elif after_status == "PASS" and before.current_status != "PASS":
        outcome = "IMPROVED"
    else:
        before_rank = _STAGE_ORDER.get(before.current_stop_stage or "", -1)
        after_rank = _STAGE_ORDER.get(after_stage, -1)
        if after_rank > before_rank:
            outcome = "IMPROVED"
        elif after_rank < before_rank:
            outcome = "REGRESSED"
        else:
            outcome = "UNCHANGED"
    return RunComparison(
        claim_id=claim_id,
        before_status=before.current_status,
        before_reason=before.current_reason,
        before_stage=before.current_stop_stage,
        after_status=after_status,
        after_reason=after_reason,
        after_stage=after_stage,
        outcome=outcome,
        official_evidence=bool(after.get("official_evidence")),
        table_id=_text(after.get("table_id")),
        source_url=_text(after.get("source_url")),
    )


def record_group_run(
    records: list[ClaimIssueRecord],
    group: IssueGroup,
    results: list[dict[str, Any]],
    *,
    output_dir: Path,
    run_id: str,
    code_version: str,
    data_version: str,
) -> list[RunComparison]:
    """Persist an auditable before/after ledger and update the master rows."""

    if not run_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for character in run_id):
        raise ValueError("INVALID_RUN_ID")
    before_by_id = {
        record.claim_id: record
        for record in records
        if record.primary_group is group
    }
    result_ids = [str(result.get("claim_id") or "") for result in results]
    if len(result_ids) != len(set(result_ids)):
        raise ValueError("DUPLICATE_RUN_RESULT")
    if any(claim_id not in before_by_id for claim_id in result_ids):
        raise ValueError("RUN_RESULT_OUTSIDE_GROUP")
    comparisons = [
        compare_result(before_by_id[claim_id], result)
        for claim_id, result in zip(result_ids, results, strict=True)
    ]
    recorded_at = _utc_now()
    run_rows = [
        {
            "실행번호": run_id,
            "Claim번호": item.claim_id,
            "대표문제": group.value,
            "개선전상태": item.before_status,
            "개선전단계": item.before_stage or "",
            "개선전사유": item.before_reason or "",
            "개선후상태": item.after_status,
            "개선후단계": item.after_stage or "",
            "개선후사유": item.after_reason or "",
            "개선판정": item.outcome,
            "공식근거확인": "예" if item.official_evidence else "아니오",
            "공식통계표": item.table_id or "",
            "공식값출처": item.source_url or "",
            "코드버전": code_version,
            "데이터버전": data_version,
            "기록시각": recorded_at,
        }
        for item in comparisons
    ]
    run_dir = output_dir / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_csv_atomic(run_dir / f"{run_id}.csv", _RUN_HEADERS, run_rows)
    _update_master_after_run(
        output_dir / "claim_issue_master.csv",
        comparisons,
        code_version=code_version,
        data_version=data_version,
        recorded_at=recorded_at,
    )
    _update_group_summary(
        output_dir / "claim_issue_master.csv",
        output_dir / "group_summary.csv",
        group,
    )
    return comparisons


def evaluate_group_gate(
    group: IssueGroup,
    comparisons: list[RunComparison],
    *,
    expected_claim_ids: set[str],
    gate_dir: Path,
    code_version: str,
    data_version: str,
) -> GroupGateResult:
    """Persist a version-bound group gate after complete before/after evidence."""

    reasons: list[str] = []
    observed = {item.claim_id for item in comparisons}
    for claim_id in sorted(expected_claim_ids - observed):
        reasons.append(f"MISSING_COMPARISON:{claim_id}")
    for claim_id in sorted(observed - expected_claim_ids):
        reasons.append(f"UNEXPECTED_COMPARISON:{claim_id}")
    for item in comparisons:
        if item.outcome not in {"IMPROVED", "RESOLVED"}:
            reasons.append(f"{item.outcome}:{item.claim_id}")
        if group in _OFFICIAL_GROUPS and not item.official_evidence:
            reasons.append(f"MISSING_OFFICIAL_EVIDENCE:{item.claim_id}")
    evaluated_at = _utc_now()
    gate = GroupGateResult(
        group=group,
        passed=not reasons and bool(expected_claim_ids),
        reasons=tuple(reasons or ()),
        code_version=code_version,
        data_version=data_version,
        evaluated_at=evaluated_at,
    )
    gate_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        gate_dir / f"{group.value}.json",
        {
            "group": group.value,
            "passed": gate.passed,
            "reasons": list(gate.reasons),
            "expected_claim_count": len(expected_claim_ids),
            "comparison_count": len(comparisons),
            "code_version": code_version,
            "data_version": data_version,
            "evaluated_at": evaluated_at,
        },
    )
    return gate


def _update_master_after_run(
    path: Path,
    comparisons: list[RunComparison],
    *,
    code_version: str,
    data_version: str,
    recorded_at: str,
) -> None:
    if not path.is_file():
        return
    comparison_by_id = {item.claim_id: item for item in comparisons}
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        item = comparison_by_id.get(row.get("Claim번호") or "")
        if item is None:
            continue
        row["개선후상태"] = item.after_status
        row["개선후사유"] = item.after_reason or ""
        row["개선판정"] = item.outcome
        row["공식통계표"] = item.table_id or ""
        row["공식값출처"] = item.source_url or ""
        row["실행횟수"] = int(row.get("실행횟수") or 0) + 1
        row["코드버전"] = code_version
        row["데이터버전"] = data_version
        row["기록시각"] = recorded_at
    _write_csv_atomic(path, _LEDGER_HEADERS, rows)


def _update_group_summary(
    master_path: Path,
    summary_path: Path,
    group: IssueGroup,
) -> None:
    if not master_path.is_file() or not summary_path.is_file():
        return
    with master_path.open(encoding="utf-8-sig", newline="") as source:
        master_rows = [
            row
            for row in csv.DictReader(source)
            if row.get("대표문제") == group.value
        ]
    attempted = sum(int(row.get("실행횟수") or 0) > 0 for row in master_rows)
    improved = sum(
        row.get("개선판정") in {"IMPROVED", "RESOLVED"}
        for row in master_rows
    )
    remaining = max(0, len(master_rows) - improved)
    headers = ("문제코드", "전체수", "시도수", "개선수", "남은수", "완료여부")
    with summary_path.open(encoding="utf-8-sig", newline="") as source:
        summary_rows = list(csv.DictReader(source))
    for row in summary_rows:
        if row.get("문제코드") != group.value:
            continue
        row["전체수"] = len(master_rows)
        row["시도수"] = attempted
        row["개선수"] = improved
        row["남은수"] = remaining
        row["완료여부"] = "예" if master_rows and not remaining else "아니오"
    _write_csv_atomic(summary_path, headers, summary_rows)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class FinalRunAuthorization:
    authorized: bool
    reasons: tuple[str, ...]
    checked_at: str


def authorize_final_full_run(
    records: list[ClaimIssueRecord],
    *,
    gate_dir: Path,
    code_version: str,
    data_version: str,
    explicit_authorization: bool,
) -> FinalRunAuthorization:
    """Authorize, but never start, the one final full Registry execution."""

    reasons: list[str] = []
    if not explicit_authorization:
        reasons.append("EXPLICIT_FINAL_AUTHORIZATION_REQUIRED")
    unclassified = sum(
        record.primary_group is IssueGroup.UNCLASSIFIED for record in records
    )
    if unclassified:
        reasons.append(f"UNCLASSIFIED_CLAIMS_REMAIN:{unclassified}")

    required_groups = sorted(
        {
            record.primary_group
            for record in records
            if record.primary_group
            not in {IssueGroup.REGRESSION, IssueGroup.UNCLASSIFIED}
        },
        key=lambda group: group.value,
    )
    for group in required_groups:
        path = gate_dir / f"{group.value}.json"
        if not path.is_file():
            reasons.append(f"MISSING_GROUP_GATE:{group.value}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reasons.append(f"INVALID_GROUP_GATE:{group.value}")
            continue
        if not isinstance(payload, dict) or payload.get("group") != group.value:
            reasons.append(f"INVALID_GROUP_GATE:{group.value}")
            continue
        if not payload.get("passed"):
            reasons.append(f"FAILED_GROUP_GATE:{group.value}")
        if (
            payload.get("code_version") != code_version
            or payload.get("data_version") != data_version
        ):
            reasons.append(f"STALE_GROUP_GATE:{group.value}")

    return FinalRunAuthorization(
        authorized=not reasons,
        reasons=tuple(reasons),
        checked_at=_utc_now(),
    )
