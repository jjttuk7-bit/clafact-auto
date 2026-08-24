"""Human-readable CSV export for bounded official verification runs."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from core.hard_guard_diagnostics import format_hard_guard_rejections
from schemas.claim_registry import ClaimRegistryRecord


_STAGE_NAMES = {
    "CLAIM_PARSE": "12개항목확인",
    "SEMANTIC_MAPPING": "의미표준연결",
    "CATALOG_SEARCH": "통계표검색",
    "KOSIS_METADATA": "공식구조조회",
    "HARD_GUARD": "기본조건검사",
    "SEMANTIC_MATCH": "후보정밀비교",
    "OFFICIAL_AUTHOR_SEARCH": "작성기관검색",
    "OFFICIAL_AUTHOR_FETCH": "공식문서조회",
    "EVIDENCE_CELL": "공식좌표확정",
    "OFFICIAL_VALUE_FETCH": "공식값조회",
    "CALCULATION": "계산",
    "VERDICT": "판정",
}
_STATUS_NAMES = {"PASS": "통과", "HOLD": "중단", "FAIL": "실패"}

_HEADERS = (
    "기사번호", "문장번호", "부모Claim번호", "자식Claim번호", "원문",
    "지표", "기사수치", "단위", "시점", "계산방식", "12개항목상태",
    "의미표준", "후보통계표", "조건검사탈락사유", "공식좌표", "단계별결과",
    "공식API조회여부", "통계표검색시도", "항목메타조회시도", "기간메타조회시도",
    "공식값조회성공", "공식값", "공표확인", "공식값URL", "공표URL",
    "응답해시", "공표해시", "계산값", "판정", "최종상태", "중단단계",
    "중단사유", "코드버전", "자료버전", "실행시각",
    "작성기관보조경로", "공식작성기관", "공식문서상태", "공식문서URL", "공식문서조회시각", "공식문서해시",
)


def write_official_run_csv(
    records: list[ClaimRegistryRecord],
    results: list[dict[str, Any]],
    path: Path,
    *,
    code_version: str,
    data_version: str,
) -> None:
    result_by_id = {str(row.get("claim_id") or ""): row for row in results}
    expected_ids = {record.claim.claim_id for record in records}
    if set(result_by_id) != expected_ids or len(result_by_id) != len(results):
        raise ValueError("OFFICIAL_RUN_RESULT_ID_MISMATCH")
    written_at = datetime.now(timezone.utc).isoformat()
    rows = [
        _csv_row(
            record,
            result_by_id[record.claim.claim_id],
            code_version=code_version,
            data_version=data_version,
            written_at=written_at,
        )
        for record in records
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _csv_row(
    record: ClaimRegistryRecord,
    result: dict[str, Any],
    *,
    code_version: str,
    data_version: str,
    written_at: str,
) -> dict[str, object]:
    claim = record.claim
    resolution = _dict(result.get("official_resolution"))
    verdict = _dict(resolution.get("verdict"))
    concept = _dict(resolution.get("concept"))
    diagnostics = _dict(resolution.get("catalog_diagnostics"))
    author_evidence = _dict(resolution.get("official_author_evidence"))
    trace = _dict(verdict.get("execution_trace"))
    events = [event for event in trace.get("events") or [] if isinstance(event, dict)]
    provenance = [
        item for item in verdict.get("official_value_provenance") or []
        if isinstance(item, dict)
    ]
    publications = [
        item["publication"] for item in provenance
        if isinstance(item.get("publication"), dict)
    ]
    candidates = [
        item for item in resolution.get("candidates") or [] if isinstance(item, dict)
    ]
    terminal_status = str(result.get("terminal_status") or verdict.get("route_status") or "")
    stop_event = (
        next((event for event in reversed(events) if event.get("status") in {"HOLD", "FAIL"}), None)
        if terminal_status != "AUTO"
        else None
    )
    api_rows = [item for item in provenance if item.get("source") == "API"]
    return {
        "기사번호": record.article_id,
        "문장번호": record.sentence_id,
        "부모Claim번호": record.source_metadata.get("parent_claim_id") or "",
        "자식Claim번호": claim.claim_id,
        "원문": claim.source_sentence,
        "지표": claim.indicator or "",
        "기사수치": claim.value if claim.value is not None else "",
        "단위": claim.unit or "",
        "시점": claim.time or "",
        "계산방식": claim.calculation or "",
        "12개항목상태": _slot_summary(result.get("slot_audit")),
        "의미표준": concept.get("canonical_name") or concept.get("standard_key") or "",
        "후보통계표": " | ".join(_unique(str(item.get("tbl_id") or "") for item in candidates)),
        "조건검사탈락사유": format_hard_guard_rejections(diagnostics),
        "공식좌표": _json(verdict.get("evidence_cells") or []),
        "단계별결과": " | ".join(_event_text(event) for event in events),
        "공식API조회여부": "예" if (
            int(diagnostics.get("attempted_queries") or 0) > 0
            or int(diagnostics.get("kosis_catalog_unavailable") or 0) > 0
        ) else "아니오",
        "통계표검색시도": int(diagnostics.get("attempted_queries") or 0),
        "항목메타조회시도": int(diagnostics.get("metadata_itm_attempted") or 0),
        "기간메타조회시도": int(diagnostics.get("metadata_prd_attempted") or 0),
        "공식값조회성공": "예" if api_rows else "아니오",
        "공식값": _json(verdict.get("evidence_values") or []),
        "공표확인": _publication_status(publications),
        "공식값URL": " | ".join(_unique(str(item.get("source_url") or "") for item in api_rows)),
        "공표URL": " | ".join(_unique(str(item.get("source_url") or "") for item in publications)),
        "응답해시": " | ".join(_unique(str(item.get("content_hash") or "") for item in api_rows)),
        "공표해시": " | ".join(_unique(str(item.get("content_hash") or "") for item in publications)),
        "작성기관보조경로": "예" if int(diagnostics.get("official_author_fallback_attempted") or 0) > 0 else "아니오",
        "공식작성기관": author_evidence.get("author_name") or "",
        "공식문서상태": author_evidence.get("status") or "",
        "공식문서URL": author_evidence.get("source_url") or "",
        "공식문서조회시각": author_evidence.get("retrieved_at") or "",
        "공식문서해시": author_evidence.get("content_hash") or "",
        "계산값": verdict.get("calculated_value") if verdict.get("calculated_value") is not None else "",
        "판정": verdict.get("verdict") or "",
        "최종상태": result.get("terminal_status") or verdict.get("route_status") or "",
        "중단단계": _STAGE_NAMES.get(str(stop_event.get("stage")), str(stop_event.get("stage"))) if stop_event else "",
        "중단사유": result.get("reason_code") or verdict.get("reason_code") or "",
        "코드버전": code_version,
        "자료버전": data_version,
        "실행시각": written_at,
    }


def _event_text(event: dict[str, Any]) -> str:
    stage = str(event.get("stage") or "UNKNOWN")
    status = str(event.get("status") or "UNKNOWN")
    text = f"{_STAGE_NAMES.get(stage, stage)}={_STATUS_NAMES.get(status, status)}"
    reason = str(event.get("reason_code") or "")
    return f"{text}({reason})" if reason else text


def _slot_summary(value: object) -> str:
    audit = _dict(value)
    return " | ".join(
        f"{entry.get('slot')}={entry.get('status')}"
        for entry in audit.get("entries") or []
        if isinstance(entry, dict) and entry.get("slot") and entry.get("status")
    )


def _publication_status(publications: list[dict[str, Any]]) -> str:
    if publications and all(item.get("status") == "VERIFIED" for item in publications):
        return "확인"
    if any(item.get("status") == "FETCH_FAILED" for item in publications):
        return "조회실패"
    return "미확인"


def _unique(values: object) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))  # type: ignore[union-attr]


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
