"""Dashboard-path acceptance rules for completed parent Claims."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
import json
from typing import Any, Iterable, Sequence


DASHBOARD_LEDGER_HEADERS = (
    "대시보드검증상태",
    "대시보드기사작성일",
    "대시보드코드버전",
    "대시보드최종상태",
    "대시보드판정",
    "대시보드중단사유",
    "대시보드중단단계",
    "대시보드공식근거확인",
    "대시보드공식근거URL",
    "대시보드응답해시",
    "대시보드실행번호",
    "대시보드검증시각",
)


@dataclass(frozen=True, slots=True)
class AcceptanceCase:
    parent_claim_id: str
    article_id: str
    article_published_at: date
    article_text: str
    expected_verdicts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DashboardAcceptanceResult:
    parent_claim_id: str
    article_id: str
    article_published_at: str
    article_text: str
    expected_verdicts: str
    derived_claim_count: int
    child_claim_ids: str
    actual_status: str
    actual_verdicts: str
    failure_reason: str
    failure_stage: str
    official_evidence_verified: str
    table_ids: str
    coordinates: str
    official_values: str
    calculated_values: str
    source_urls: str
    response_hashes: str
    acceptance_status: str
    run_id: str
    recorded_at: str = ""


def verify_dashboard_article(
    runtime: Any,
    article_text: str,
    *,
    article_published_at: date | None,
):
    """One boundary shared by the Streamlit single-Claim UI and acceptance run."""
    return runtime.verify_article(
        article_text,
        article_published_at=article_published_at,
    )


def registry_article_dates(root: Path) -> dict[str, date]:
    """Read consistent parent Claim dates from Registry-shaped JSONL files."""
    result: dict[str, date] = {}
    for path in sorted(root.rglob("*.jsonl")):
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
            claim_id = str(claim.get("claim_id") or "") if isinstance(claim, dict) else ""
            raw_date = payload.get("article_published_at")
            if not claim_id or not raw_date:
                continue
            parsed = date.fromisoformat(str(raw_date))
            previous = result.get(claim_id)
            if previous is not None and previous != parsed:
                raise ValueError(f"CONFLICTING_ARTICLE_DATE:{claim_id}")
            result[claim_id] = parsed
    return result


def select_completed_cases(
    ledger_rows: Sequence[dict[str, str]],
    article_dates: dict[str, date],
) -> list[AcceptanceCase]:
    cases: list[AcceptanceCase] = []
    for row in ledger_rows:
        if str(row.get("남은작업") or "") != "완료":
            continue
        claim_id = str(row.get("Claim번호") or "").strip()
        if claim_id not in article_dates:
            raise ValueError(f"ARTICLE_DATE_NOT_FOUND:{claim_id}")
        text = str(row.get("원문") or "").strip()
        if not text:
            raise ValueError(f"ARTICLE_TEXT_NOT_FOUND:{claim_id}")
        expected = _parts(row.get("최신판정"))
        if not expected:
            raise ValueError(f"EXPECTED_VERDICT_NOT_FOUND:{claim_id}")
        cases.append(AcceptanceCase(
            parent_claim_id=claim_id,
            article_id=str(row.get("기사번호") or "").strip(),
            article_published_at=article_dates[claim_id],
            article_text=text,
            expected_verdicts=expected,
        ))
    return cases


def evaluate_dashboard_result(
    case: AcceptanceCase,
    result: Any,
    *,
    run_id: str,
) -> DashboardAcceptanceResult:
    entries = list(getattr(result, "entries", []) or [])
    child_ids: list[str] = []
    statuses: list[str] = []
    verdicts: list[str] = []
    reasons: list[str] = []
    stages: list[str] = []
    tables: list[str] = []
    coordinates: list[str] = []
    official_values: list[str] = []
    calculated_values: list[str] = []
    urls: list[str] = []
    hashes: list[str] = []
    all_official = bool(entries)
    for entry in entries:
        claim = getattr(entry, "claim", None)
        child_ids.append(str(getattr(claim, "claim_id", "")))
        status = str(getattr(entry, "terminal_status", "HOLD") or "HOLD")
        statuses.append(status)
        resolution = getattr(entry, "official_resolution", None)
        verdict = getattr(resolution, "verdict", None) if resolution is not None else None
        stage = _entry_failure_stage(entry, verdict)
        if status != "AUTO" and stage:
            stages.append(stage)
        if verdict is None:
            all_official = False
            reasons.append(str(getattr(entry, "reason_code", None) or "OFFICIAL_RESOLUTION_NOT_ATTEMPTED"))
            continue
        verdicts.append(str(getattr(verdict, "verdict", "UNDETERMINED")))
        reason = str(getattr(verdict, "reason_code", "") or "")
        if status != "AUTO" and reason:
            reasons.append(reason)
        for cell in getattr(verdict, "evidence_cells", []) or []:
            tables.append(str(getattr(cell, "tbl_id", "") or ""))
            coordinates.append(str(getattr(cell, "canonical_key", "") or ""))
        official_values.extend(str(value) for value in getattr(verdict, "evidence_values", []) or [])
        calculated = getattr(verdict, "calculated_value", None)
        if calculated is not None:
            calculated_values.append(str(calculated))
        provenance = list(getattr(verdict, "official_value_provenance", []) or [])
        if not provenance:
            all_official = False
        for item in provenance:
            source = str(getattr(item, "source", ""))
            publication = getattr(item, "publication", None)
            publication_status = str(getattr(publication, "status", ""))
            if source not in {"API", "OFFICIAL_DOCUMENT"} or publication_status != "VERIFIED":
                all_official = False
            urls.append(str(getattr(item, "source_url", "") or ""))
            hashes.append(str(getattr(item, "content_hash", "") or ""))
    actual_status = "AUTO" if entries and all(status == "AUTO" for status in statuses) else "HOLD"
    actual_verdicts = _join(verdicts)
    expected_verdicts = _join(case.expected_verdicts)
    failure_reason = _join(reasons)
    if not entries:
        failure_reason = "NO_NUMERICAL_CLAIM_CANDIDATE"
    elif actual_status != "AUTO":
        failure_reason = failure_reason or "DASHBOARD_CHILD_HOLD"
    elif not all_official:
        failure_reason = "DASHBOARD_OFFICIAL_EVIDENCE_INCOMPLETE"
    elif set(_parts(actual_verdicts)) != set(case.expected_verdicts):
        failure_reason = "DASHBOARD_VERDICT_MISMATCH"
    accepted = not failure_reason
    return DashboardAcceptanceResult(
        parent_claim_id=case.parent_claim_id,
        article_id=case.article_id,
        article_published_at=case.article_published_at.isoformat(),
        article_text=case.article_text,
        expected_verdicts=expected_verdicts,
        derived_claim_count=len(entries),
        child_claim_ids=_join(child_ids),
        actual_status=actual_status,
        actual_verdicts=actual_verdicts,
        failure_reason=failure_reason,
        failure_stage=_join(stages) if failure_reason else "",
        official_evidence_verified="예" if all_official else "아니오",
        table_ids=_join(tables),
        coordinates=_join(coordinates),
        official_values=_join(official_values),
        calculated_values=_join(calculated_values),
        source_urls=_join(urls),
        response_hashes=_join(hashes),
        acceptance_status="통과" if accepted else "실패",
        run_id=run_id,
    )


def failed_dashboard_result(
    case: AcceptanceCase, *, run_id: str, reason: str
) -> DashboardAcceptanceResult:
    empty = evaluate_dashboard_result(case, None, run_id=run_id)
    return replace(
        empty,
        failure_reason=reason,
        failure_stage=failure_stage_from_reason(reason),
        acceptance_status="실패",
    )


def apply_acceptance_to_ledger(
    ledger_rows: Sequence[dict[str, str]],
    results: Iterable[DashboardAcceptanceResult],
    *,
    code_version: str,
) -> list[dict[str, str]]:
    by_parent = {item.parent_claim_id: item for item in results}
    updated: list[dict[str, str]] = []
    for source in ledger_rows:
        row = dict(source)
        for header in DASHBOARD_LEDGER_HEADERS:
            row.setdefault(header, "")
        item = by_parent.get(str(row.get("Claim번호") or ""))
        if item is not None:
            row.update({
                "대시보드검증상태": item.acceptance_status,
                "대시보드기사작성일": item.article_published_at,
                "대시보드코드버전": code_version,
                "대시보드최종상태": item.actual_status,
                "대시보드판정": item.actual_verdicts,
                "대시보드중단사유": item.failure_reason,
                "대시보드중단단계": item.failure_stage,
                "대시보드공식근거확인": item.official_evidence_verified,
                "대시보드공식근거URL": item.source_urls,
                "대시보드응답해시": item.response_hashes,
                "대시보드실행번호": item.run_id,
                "대시보드검증시각": item.recorded_at,
            })
            if item.acceptance_status == "통과":
                row["남은작업"] = "완료"
            else:
                row["남은작업"] = "대시보드 재현 실패"
                row["현재문제묶음"] = _issue_group(item.failure_stage, item.failure_reason)
        updated.append(row)
    return updated


def _entry_failure_stage(entry: Any, verdict: Any | None) -> str:
    if verdict is not None:
        trace = getattr(verdict, "execution_trace", None)
        events = list(getattr(trace, "events", []) or [])
        held = [event for event in events if str(getattr(event, "status", "")) == "HOLD"]
        if held:
            return str(getattr(held[-1], "stage", ""))
    stage_results = list(getattr(entry, "stage_results", []) or [])
    held_results = [item for item in stage_results if str(getattr(item, "status", "")) == "HOLD"]
    if held_results:
        return str(getattr(held_results[-1], "stage", ""))
    route = str(getattr(entry, "admission_route", "") or "")
    if route == "MULTI_CLAIM_SPLIT_REQUIRED":
        return "CLAIM_SPLIT"
    if route in {"CONTEXT_REQUIRED", "STRUCTURAL_HOLD"}:
        return "CLAIM_PARSE"
    return failure_stage_from_reason(str(getattr(entry, "reason_code", "") or ""))


def failure_stage_from_reason(reason: str) -> str:
    if "CLAIM_SPLIT" in reason:
        return "CLAIM_SPLIT"
    if "CLAIM_PARSE" in reason or "MISSING_REQUIRED_SLOTS" in reason or "TARGET_VALUE" in reason:
        return "CLAIM_PARSE"
    if "CONCEPT" in reason or "SEMANTIC" in reason:
        return "SEMANTIC_MAPPING"
    if "CATALOG" in reason:
        return "CATALOG_SEARCH"
    if "METADATA" in reason:
        return "KOSIS_METADATA"
    if "NO_EVIDENCE_COORDINATE" in reason:
        return "EVIDENCE_CELL"
    if "HARD_GUARD" in reason or "AMBIGUOUS_MARGIN" in reason:
        return "HARD_GUARD"
    if "AS_OF" in reason or "PUBLICATION" in reason:
        return "PUBLICATION"
    if "FETCH" in reason:
        return "OFFICIAL_VALUE_FETCH"
    if "CALCULATION" in reason:
        return "CALCULATION"
    return "CLAIM_PARSE" if reason else ""


def _issue_group(stage: str, reason: str) -> str:
    if "NO_EVIDENCE_COORDINATE" in reason or "EVIDENCE_CELL" in stage:
        return "COORDINATE"
    if "CLAIM_PARSE" in stage or "CLAIM_SPLIT" in stage:
        return "CONTEXT"
    if "HARD_GUARD" in reason:
        return "HARD_GUARD"
    if "CONCEPT" in reason or "SEMANTIC" in reason:
        return "SEMANTIC"
    if "CATALOG" in reason or "METADATA" in reason or "OFFICIAL_AUTHOR" in reason:
        return "OFFICIAL_PATH"
    if "FETCH" in reason or "AS_OF" in reason or "PUBLICATION" in reason:
        return "VALUE_PUBLICATION"
    if "CALCULATION" in reason:
        return "CALCULATION"
    if "CLAIM" in reason or "CONTEXT" in reason or "SPLIT" in reason:
        return "CONTEXT"
    if "SEMANTIC_MAPPING" in stage:
        return "SEMANTIC"
    if "CATALOG_SEARCH" in stage or "KOSIS_METADATA" in stage:
        return "OFFICIAL_PATH"
    if "HARD_GUARD" in stage:
        return "HARD_GUARD"
    if "PUBLICATION" in stage or "OFFICIAL_VALUE_FETCH" in stage:
        return "VALUE_PUBLICATION"
    if "CALCULATION" in stage:
        return "CALCULATION"
    return "REGRESSION"


def _parts(value: object) -> tuple[str, ...]:
    return tuple(sorted({
        part.strip()
        for part in str(value or "").split("|")
        if part.strip()
    }))


def _join(values: Iterable[object]) -> str:
    return "|".join(sorted({str(value).strip() for value in values if str(value).strip()}))
