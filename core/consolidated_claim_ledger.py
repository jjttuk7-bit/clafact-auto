"""Deterministically rebuild one parent-Claim ledger from distributed run results."""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable, Sequence


EXTRA_HEADERS = (
    "최신결과상태",
    "최신결과단계",
    "최신결과사유",
    "최신개선판정",
    "최신자식Claim번호",
    "최신공식조회여부",
    "최신공식통계표",
    "최신공식좌표",
    "최신공식값",
    "최신계산값",
    "최신판정",
    "최신공표확인",
    "최신공식값출처",
    "최신결과출처",
    "최신실행번호",
    "최신기록시각",
    "반영된결과수",
    "남은작업",
    "현재문제묶음",
)


@dataclass(frozen=True, slots=True)
class LedgerUpdate:
    parent_claim_id: str
    child_claim_id: str
    status: str
    stage: str
    reason: str
    outcome: str
    official_api: str
    table_id: str
    coordinate: str
    official_value: str
    calculated_value: str
    verdict: str
    publication: str
    source_url: str
    source_path: str
    run_id: str
    recorded_at: str


def consolidate_rows(
    master_rows: Sequence[dict[str, str]],
    updates: Sequence[LedgerUpdate],
) -> list[dict[str, str]]:
    """Return master rows with the latest complete event projected onto each parent."""
    copied = [dict(row) for row in master_rows]
    master_ids = [str(row.get("Claim번호") or "") for row in copied]
    if not all(master_ids):
        raise ValueError("MASTER_CLAIM_ID_MISSING")
    if len(master_ids) != len(set(master_ids)):
        raise ValueError("MASTER_CLAIM_ID_DUPLICATE")
    master_set = set(master_ids)
    for update in updates:
        if update.parent_claim_id not in master_set:
            raise ValueError(f"RESULT_PARENT_NOT_IN_MASTER:{update.parent_claim_id}")
    _reject_conflicts(updates)

    updates = _enrich_completion_gates(updates)
    by_parent: dict[str, list[LedgerUpdate]] = {}
    for update in updates:
        by_parent.setdefault(update.parent_claim_id, []).append(update)

    for row in copied:
        claim_id = str(row["Claim번호"])
        history = sorted(by_parent.get(claim_id, []), key=_update_order)
        for header in EXTRA_HEADERS:
            row.setdefault(header, "")
        if not history:
            continue
        latest_key = _event_key(history[-1])
        current = [item for item in history if _event_key(item) == latest_key]
        status = _aggregate_status(item.status for item in current)
        reason = _join(item.reason for item in current)
        outcome = _join(item.outcome for item in current)
        official_api = _aggregate_official(item.official_api for item in current)
        current_child_ids = {item.child_claim_id for item in current}
        details = {
            "table_id": _current_detail(current, "table_id"),
            "coordinate": _current_detail(current, "coordinate"),
            "official_value": _current_detail(current, "official_value"),
            "calculated_value": _current_detail(current, "calculated_value"),
            "verdict": _current_detail(current, "verdict"),
            "publication": _current_detail(current, "publication"),
            "source_url": _current_detail(current, "source_url"),
        }
        child_ids = _join(item.child_claim_id for item in current)
        source_paths = _join(item.source_path for item in current)
        run_ids = _join(item.run_id for item in current)
        stage = _join(item.stage for item in current)
        row.update({
            "개선후상태": status,
            "개선후사유": reason,
            "개선판정": outcome,
            "공식통계표": details["table_id"],
            "공식값출처": details["source_url"],
            "최신결과상태": status,
            "최신결과단계": stage,
            "최신결과사유": reason,
            "최신개선판정": outcome,
            "최신자식Claim번호": child_ids,
            "최신공식조회여부": official_api,
            "최신공식통계표": details["table_id"],
            "최신공식좌표": details["coordinate"],
            "최신공식값": details["official_value"],
            "최신계산값": details["calculated_value"],
            "최신판정": details["verdict"],
            "최신공표확인": details["publication"],
            "최신공식값출처": details["source_url"],
            "최신결과출처": source_paths,
            "최신실행번호": run_ids,
            "최신기록시각": current[0].recorded_at,
            "반영된결과수": str(len(history)),
            "남은작업": _remaining_work(row, status, reason, details["verdict"]),
            "현재문제묶음": _current_issue_group(row, reason, stage),
        })
        row["실행횟수"] = str(max(int(row.get("실행횟수") or 0), len(history)))
    return copied


def build_child_parent_index(
    roots: Sequence[Path], master_ids: set[str],
) -> dict[str, str]:
    """Read only explicit parent lineage from Registry-shaped JSONL files."""
    index: dict[str, str] = {}
    for root in roots:
        for path in sorted(root.rglob("*registry*.jsonl")):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"INVALID_REGISTRY_JSON:{path}:{line_number}") from error
                if not isinstance(payload, dict):
                    continue
                claim = payload.get("claim")
                child = str(claim.get("claim_id") or "") if isinstance(claim, dict) else ""
                parent = _registry_parent(payload)
                if not child or not parent or parent not in master_ids:
                    continue
                previous = index.get(child)
                if previous is not None and previous != parent:
                    raise ValueError(f"CONFLICTING_CHILD_PARENT:{child}")
                index[child] = parent
    return index


def discover_updates(
    roots: Sequence[Path],
    master_ids: set[str],
    child_parent: dict[str, str],
) -> list[LedgerUpdate]:
    """Discover recognized result CSVs under explicitly supplied roots."""
    updates: list[LedgerUpdate] = []
    for root in roots:
        for path in sorted(root.rglob("*.csv")):
            if _skip_csv(path):
                continue
            if (
                path.stem.startswith("record-comparison-")
                and path.with_suffix(".jsonl").exists()
            ):
                continue
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                headers = set(reader.fieldnames or [])
                rows = list(reader)
            adapter = _adapter(headers)
            if adapter is None:
                continue
            source_path = _display_path(path, root)
            fallback_time = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat()
            for row in rows:
                update = adapter(
                    row,
                    master_ids=master_ids,
                    child_parent=child_parent,
                    source_path=source_path,
                    fallback_time=fallback_time,
                )
                if update is not None:
                    updates.append(update)
        for path in sorted(root.rglob("*.jsonl")):
            if not _is_result_jsonl(path):
                continue
            source_path = _display_path(path, root)
            fallback_time = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat()
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"INVALID_RESULT_JSON:{path}:{line_number}") from error
                if not isinstance(payload, dict):
                    continue
                updates.append(_canonical_update(
                    payload,
                    master_ids=master_ids,
                    child_parent=child_parent,
                    source_path=source_path,
                    fallback_time=fallback_time,
                    run_id=str(payload.get("run_id") or path.parent.name),
                ))
    return updates


def output_headers(master_headers: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*master_headers, *EXTRA_HEADERS]))


def _adapter(headers: set[str]):
    if {"Claim번호", "개선후상태", "개선판정"} <= headers:
        return _harness_update
    if {"parent_claim_id", "after_status", "child_claim_id"} <= headers:
        return _record_update
    if {"부모Claim번호", "최종상태", "자식Claim번호"} <= headers:
        return _official_update
    if {"claim_id", "gate_passed", "terminal_verdict"} <= headers:
        return _gate_update
    if {"부모Claim번호", "분리판정", "재입장결과"} <= headers:
        return _multi_update
    return None


def _harness_update(row: dict[str, str], **context: object) -> LedgerUpdate | None:
    claim_id = str(row.get("Claim번호") or "").strip()
    if not claim_id:
        return None
    parent = _parent(claim_id, context)
    return _make_update(
        parent=parent, child=claim_id, status=row.get("개선후상태"),
        stage=row.get("개선후단계"), reason=row.get("개선후사유"),
        outcome=row.get("개선판정"), official=row.get("공식근거확인"),
        table=row.get("공식통계표"), source_url=row.get("공식값출처"),
        run_id=row.get("실행번호"), recorded_at=row.get("기록시각"), **context,
    )


def _record_update(row: dict[str, str], **context: object) -> LedgerUpdate:
    child = str(row.get("child_claim_id") or "").strip()
    parent = _parent(str(row.get("parent_claim_id") or ""), context, child=child)
    official = "예" if _truth(row.get("official_api_verified")) else "아니오"
    return _make_update(
        parent=parent, child=child, status=row.get("after_status"), stage="VERDICT",
        reason=row.get("after_reason"), outcome="RESOLVED" if row.get("after_status") == "AUTO" else "UNCHANGED",
        official=official, table=row.get("official_table"), source_url=row.get("source_urls"),
        verdict=_record_verdict(str(row.get("after_reason") or "")), run_id=row.get("run_id"),
        recorded_at=_stage_finished_at(row.get("stage_results_json")), **context,
    )


def _official_update(row: dict[str, str], **context: object) -> LedgerUpdate:
    child = str(row.get("자식Claim번호") or "").strip()
    parent = _parent(str(row.get("부모Claim번호") or ""), context, child=child)
    status = str(row.get("최종상태") or "")
    official = "예" if str(row.get("공식API조회여부") or "") in {"예", "true", "True"} else "아니오"
    return _make_update(
        parent=parent, child=child, status=status, stage=row.get("중단단계") or ("VERDICT" if status == "AUTO" else ""),
        reason=row.get("중단사유"), outcome="RESOLVED" if status == "AUTO" else "UNCHANGED",
        official=official, table=row.get("후보통계표"), coordinate=row.get("공식좌표"),
        official_value=row.get("공식값"), calculated=row.get("계산값"), verdict=row.get("판정"),
        publication=row.get("공표확인"), source_url=row.get("공식값URL"), recorded_at=row.get("실행시각"),
        **context,
    )


def _gate_update(row: dict[str, str], **context: object) -> LedgerUpdate:
    child = str(row.get("claim_id") or "").strip()
    parent = _parent(child, context, child=child)
    passed = _truth(row.get("gate_passed"))
    official_cells = int(row.get("official_api_cells") or 0)
    publication_cells = int(row.get("publication_verified_cells") or 0)
    return _make_update(
        parent=parent, child=child, status="AUTO" if passed else "HOLD", stage="VERDICT",
        reason=row.get("terminal_reason") or row.get("gate_reasons"),
        outcome="RESOLVED" if passed else "UNCHANGED", official="예" if official_cells > 0 else "아니오",
        official_value=row.get("official_values"), calculated=row.get("calculated_value"),
        verdict=row.get("terminal_verdict"), publication=f"{publication_cells}/{official_cells}",
        **context,
    )


def _multi_update(row: dict[str, str], **context: object) -> LedgerUpdate:
    child = str(row.get("자식Claim번호") or "").strip()
    parent = _parent(str(row.get("부모Claim번호") or ""), context, child=child)
    route = str(row.get("재입장결과") or "")
    passed = str(row.get("분리판정") or "").upper() in {"PASS", "MATCH"} and route == "KOSIS_PIPELINE_ELIGIBLE"
    return _make_update(
        parent=parent, child=child, status="PASS" if passed else "HOLD", stage="CLAIM_PARSE",
        reason=row.get("중단사유") or route, outcome="IMPROVED" if passed else "UNCHANGED",
        official="아니오", recorded_at=row.get("실행시각"), **context,
    )


def _canonical_update(payload: dict[str, object], **context: object) -> LedgerUpdate:
    child = str(payload.get("claim_id") or "")
    parent = _canonical_parent(payload, child, context)
    resolution = payload.get("official_resolution")
    resolution = resolution if isinstance(resolution, dict) else {}
    verdict = resolution.get("verdict")
    verdict = verdict if isinstance(verdict, dict) else {}
    evidence = [item for item in verdict.get("evidence_cells") or [] if isinstance(item, dict)]
    provenance = [item for item in verdict.get("official_value_provenance") or [] if isinstance(item, dict)]
    trace = verdict.get("execution_trace")
    trace = trace if isinstance(trace, dict) else {}
    events = [item for item in trace.get("events") or [] if isinstance(item, dict)]
    stage = str(events[-1].get("stage") or "") if events else ""
    tables = _join(str(item.get("tbl_id") or "") for item in evidence)
    coordinates = _join(str(item.get("canonical_key") or "") for item in evidence)
    values = "|".join(str(value) for value in verdict.get("evidence_values") or [])
    api_count = sum(item.get("source") == "API" for item in provenance)
    publication_count = sum(
        isinstance(item.get("publication"), dict)
        and item["publication"].get("status") == "VERIFIED"
        for item in provenance
    )
    urls = _join(str(item.get("source_url") or "") for item in provenance)
    status = str(payload.get("terminal_status") or verdict.get("route_status") or "")
    return _make_update(
        parent=parent,
        child=child,
        status=status,
        stage=stage,
        reason=payload.get("reason_code") or verdict.get("reason_code"),
        outcome="RESOLVED" if status == "AUTO" else "UNCHANGED",
        official="예" if provenance and api_count == len(provenance) else "아니오",
        table=tables,
        coordinate=coordinates,
        official_value=values,
        calculated=verdict.get("calculated_value"),
        verdict=verdict.get("verdict"),
        publication=f"{publication_count}/{len(provenance)}" if provenance else "",
        source_url=urls,
        recorded_at=_payload_finished_at(payload),
        **context,
    )


def _make_update(
    *, parent: str, child: str, status: object = "", stage: object = "",
    reason: object = "", outcome: object = "", official: object = "",
    table: object = "", coordinate: object = "", official_value: object = "",
    calculated: object = "", verdict: object = "", publication: object = "",
    source_url: object = "", run_id: object = "", recorded_at: object = "",
    source_path: object, fallback_time: object, **_: object,
) -> LedgerUpdate:
    return LedgerUpdate(
        parent_claim_id=parent,
        child_claim_id=str(child or parent),
        status=str(status or ""),
        stage=str(stage or ""),
        reason=str(reason or ""),
        outcome=str(outcome or ""),
        official_api=str(official or "아니오"),
        table_id=str(table or ""),
        coordinate=str(coordinate or ""),
        official_value=str(official_value or ""),
        calculated_value=str(calculated or ""),
        verdict=str(verdict or ""),
        publication=str(publication or ""),
        source_url=str(source_url or ""),
        source_path=str(source_path),
        run_id=str(run_id or ""),
        recorded_at=str(recorded_at or fallback_time),
    )


def _parent(candidate: str, context: dict[str, object], *, child: str = "") -> str:
    master_ids = context["master_ids"]
    child_parent = context["child_parent"]
    assert isinstance(master_ids, set) and isinstance(child_parent, dict)
    if candidate in master_ids:
        return candidate
    for value in (child, candidate):
        mapped = child_parent.get(value)
        if mapped:
            return str(mapped)
    raise ValueError(f"RESULT_PARENT_NOT_IN_MASTER:{candidate or child}")


def _canonical_parent(
    payload: dict[str, object], child: str, context: dict[str, object],
) -> str:
    master_ids = context["master_ids"]
    child_parent = context["child_parent"]
    assert isinstance(master_ids, set) and isinstance(child_parent, dict)
    lineage = payload.get("lineage_record")
    candidates: list[str] = []
    if isinstance(lineage, dict):
        parent = _registry_parent(lineage)
        if parent:
            candidates.append(parent)
        source_metadata = lineage.get("source_metadata")
        if isinstance(source_metadata, dict) and source_metadata.get("claim_id"):
            candidates.append(str(source_metadata["claim_id"]))
    candidates.extend([
        str(payload.get("parent_claim_id") or ""),
        child,
        str(child_parent.get(child) or ""),
    ])
    article_id = str(payload.get("article_id") or "")
    sentence_id = str(payload.get("sentence_id") or "").split(":", 1)[0]
    if article_id and sentence_id:
        candidates.append(f"{article_id}_{sentence_id}")
    for candidate in candidates:
        if candidate in master_ids:
            return candidate
    raise ValueError(f"RESULT_PARENT_NOT_IN_MASTER:{child}")


def _registry_parent(payload: dict[str, object]) -> str:
    for container_name in ("slot_enrichment", "source_metadata"):
        container = payload.get(container_name)
        if isinstance(container, dict) and container.get("parent_claim_id"):
            return str(container["parent_claim_id"])
    return ""


def _reject_conflicts(updates: Sequence[LedgerUpdate]) -> None:
    seen: dict[tuple[str, str, str], LedgerUpdate] = {}
    for update in updates:
        key = (update.parent_claim_id, update.child_claim_id, update.recorded_at)
        previous = seen.get(key)
        if previous is not None and previous != update:
            raise ValueError(f"CONFLICTING_RESULT:{update.parent_claim_id}:{update.child_claim_id}:{update.recorded_at}")
        seen[key] = update


def _update_order(update: LedgerUpdate) -> tuple[datetime, str, str, str]:
    return (_parse_time(update.recorded_at), update.source_path, update.run_id, update.child_claim_id)


def _event_key(update: LedgerUpdate) -> tuple[datetime, str, str]:
    return (_parse_time(update.recorded_at), update.source_path, update.run_id)


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _aggregate_status(values: Iterable[str]) -> str:
    statuses = {value for value in values if value}
    if len(statuses) == 1:
        return next(iter(statuses))
    if statuses and statuses <= {"AUTO", "PASS"}:
        return "PASS"
    return "PARTIAL" if statuses else ""


def _aggregate_official(values: Iterable[str]) -> str:
    normalized = [value for value in values if value]
    if normalized and all(value == "예" for value in normalized):
        return "예"
    if any(value == "예" for value in normalized):
        return "부분"
    return "아니오"


def _enrich_completion_gates(
    updates: Sequence[LedgerUpdate],
) -> list[LedgerUpdate]:
    """Attach canonical evidence only to a later completion-gate summary event."""
    history_by_child: dict[tuple[str, str], list[LedgerUpdate]] = {}
    enriched: list[LedgerUpdate] = []
    for update in sorted(updates, key=_update_order):
        key = (update.parent_claim_id, update.child_claim_id)
        candidate = update
        if update.source_path.endswith("group_completion_gate.csv"):
            canonical = next(
                (
                    previous
                    for previous in reversed(history_by_child.get(key, []))
                    if previous.source_path.endswith("claim_verification_results.jsonl")
                    and previous.official_api == "예"
                ),
                None,
            )
            if canonical is not None:
                candidate = replace(
                    update,
                    table_id=update.table_id or canonical.table_id,
                    coordinate=update.coordinate or canonical.coordinate,
                    official_value=update.official_value or canonical.official_value,
                    calculated_value=update.calculated_value or canonical.calculated_value,
                    verdict=update.verdict or canonical.verdict,
                    publication=update.publication or canonical.publication,
                    source_url=update.source_url or canonical.source_url,
                )
        enriched.append(candidate)
        history_by_child.setdefault(key, []).append(candidate)
    return enriched


def _current_detail(current: Sequence[LedgerUpdate], field: str) -> str:
    return _join(str(getattr(update, field) or "") for update in current)


def _join(values: Iterable[str]) -> str:
    return "|".join(sorted({str(value) for value in values if value}))


def _remaining_work(row: dict[str, str], status: str, reason: str, verdict: str) -> str:
    terminal_verdicts = {
        "MATCH", "MISMATCH", "RECORD_CONFIRMED", "RECORD_REFUTED",
    }
    verdict_parts = {part for part in verdict.split("|") if part}
    if status == "AUTO" and verdict_parts and verdict_parts <= terminal_verdicts:
        return "완료"
    if status == "AUTO":
        return "최종 판정 회귀확인"
    if status == "PASS":
        return str(row.get("다음경로") or row.get("다음실행단계") or "다음 단계 실행")
    return reason or str(row.get("다음실행단계") or "미분류")


_REASON_ISSUE_GROUP = {
    "CONTEXT_REQUIRED": "CONTEXT",
    "MULTI_CLAIM_SPLIT_REQUIRED": "CONTEXT",
    "STRUCTURAL_HOLD": "CONTEXT",
    "KOSIS_CATALOG_UNAVAILABLE": "OFFICIAL_PATH",
    "KOSIS_METADATA_UNAVAILABLE": "OFFICIAL_PATH",
    "NO_HARD_GUARD_CANDIDATE": "HARD_GUARD",
    "NO_EVIDENCE_COORDINATE_CANDIDATE": "COORDINATE",
    "LOW_SEMANTIC_SCORE": "SEMANTIC",
    "AMBIGUOUS_MARGIN": "SEMANTIC",
    "CONCEPT_NOT_FOUND": "SEMANTIC",
    "CALCULATION_EVIDENCE_PLAN_UNRESOLVED": "CALCULATION",
    "CALCULATION_FAILED": "CALCULATION",
    "FETCH_FAILED": "VALUE_PUBLICATION",
    "AS_OF_UNAVAILABLE": "VALUE_PUBLICATION",
    "PUBLICATION_FETCH_FAILED": "VALUE_PUBLICATION",
}
_STAGE_ISSUE_GROUP = {
    "CLAIM_SPLIT": "CONTEXT",
    "CLAIM_PARSE": "CONTEXT",
    "SEMANTIC_MAPPING": "SEMANTIC",
    "CATALOG_SEARCH": "OFFICIAL_PATH",
    "KOSIS_METADATA": "OFFICIAL_PATH",
    "HARD_GUARD": "HARD_GUARD",
    "SEMANTIC_MATCH": "SEMANTIC",
    "EVIDENCE_CELL": "COORDINATE",
    "OFFICIAL_VALUE_FETCH": "VALUE_PUBLICATION",
    "CALCULATION": "CALCULATION",
}
_ISSUE_PRIORITY = (
    "CONTEXT", "OFFICIAL_PATH", "HARD_GUARD", "SEMANTIC",
    "COORDINATE", "VALUE_PUBLICATION", "CALCULATION",
)


def _current_issue_group(row: dict[str, str], reason: str, stage: str) -> str:
    groups = {
        _REASON_ISSUE_GROUP[token]
        for token in reason.split("|")
        if token in _REASON_ISSUE_GROUP
    }
    for group in _ISSUE_PRIORITY:
        if group in groups:
            return group
    for token in stage.split("|"):
        if token in _STAGE_ISSUE_GROUP:
            return _STAGE_ISSUE_GROUP[token]
    return str(row.get("대표문제") or "UNCLASSIFIED")


def _truth(value: object) -> bool:
    return str(value or "").strip().casefold() in {"true", "1", "yes", "예", "pass"}


def _record_verdict(reason: str) -> str:
    return {
        "WITHIN_TOLERANCE": "MATCH",
        "OUTSIDE_TOLERANCE": "MISMATCH",
    }.get(reason, reason)


def _stage_finished_at(value: object) -> str:
    if not value:
        return ""
    try:
        stages = json.loads(str(value))
    except json.JSONDecodeError:
        return ""
    if not isinstance(stages, list):
        return ""
    times = [
        str(stage.get("finished_at") or "")
        for stage in stages
        if isinstance(stage, dict) and stage.get("finished_at")
    ]
    return max(times, key=_parse_time) if times else ""


def _payload_finished_at(payload: dict[str, object]) -> str:
    stages = payload.get("stage_results")
    if not isinstance(stages, list):
        return ""
    times = [
        str(stage.get("finished_at") or "")
        for stage in stages
        if isinstance(stage, dict) and stage.get("finished_at")
    ]
    return max(times, key=_parse_time) if times else ""


def _is_result_jsonl(path: Path) -> bool:
    return path.name == "claim_verification_results.jsonl" or path.stem.startswith("record-comparison-")


def _skip_csv(path: Path) -> bool:
    return (
        path.name in {"claim_issue_master.csv", "group_summary.csv", "00_progress.csv"}
        or "groups" in path.parts
        or path.name.startswith("CLAFACT_1542_통합진행원장")
        or path.name.endswith("_children.csv")
    )


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(Path(root.name) / path.relative_to(root))
    except ValueError:
        return str(path)
