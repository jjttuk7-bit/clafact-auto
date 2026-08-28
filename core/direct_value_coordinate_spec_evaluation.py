"""Compile one auditable stage row for every direct-value coordinate scope Claim."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from typing import Any, Mapping


_STAGE_ORDER = (
    "CLAIM_PARSE", "SEMANTIC_MAPPING", "CATALOG_SEARCH", "KOSIS_METADATA",
    "HARD_GUARD", "SEMANTIC_MATCH", "EVIDENCE_CELL", "OFFICIAL_VALUE_FETCH",
    "CALCULATION", "VERDICT",
)
_STAGE_KO = {
    "CLAIM_PARSE": "사전 구조화",
    "SEMANTIC_MAPPING": "통계 개념 연결",
    "CATALOG_SEARCH": "공식 통계표 검색",
    "KOSIS_METADATA": "KOSIS 구조정보 조회",
    "HARD_GUARD": "필수 조건 검사",
    "SEMANTIC_MATCH": "후보 의미 비교",
    "EVIDENCE_CELL": "근거 좌표 확정",
    "OFFICIAL_VALUE_FETCH": "공식값 조회",
    "CALCULATION": "결정적 계산",
    "VERDICT": "최종 판정",
}


@dataclass(frozen=True, slots=True)
class CoordinateEvaluation:
    rows: tuple[dict[str, object], ...]
    summary: dict[str, object]


def compile_coordinate_evaluation(
    scope: Mapping[str, Mapping[str, object]],
    specs: Mapping[str, Mapping[str, object]],
    live_rows: list[Mapping[str, object]],
) -> CoordinateEvaluation:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for live in live_rows:
        claim_id = _text(live.get("claim_id"))
        parent_id = _text(live.get("parent_claim_id"))
        key = claim_id if claim_id in scope else parent_id
        if key in scope:
            grouped[key].append(live)

    output: list[dict[str, object]] = []
    for claim_id in sorted(scope):
        base = scope[claim_id]
        spec = specs.get(claim_id)
        if spec is None:
            raise ValueError(f"DIRECT_VALUE_176_SPEC_MISSING:{claim_id}")
        candidates = grouped.get(claim_id, [])
        live = max(candidates, key=_stage_score) if candidates else None
        output.append(_evaluation_row(claim_id, base, spec, live, len(candidates)))

    summary = {
        "scope_count": len(output),
        "coordinate_ready_count": sum(row["명세준비상태"] == "COORDINATE_READY" for row in output),
        "preverification_count": sum(row["명세준비상태"] == "PRE_VERIFICATION" for row in output),
        "semantic_pass_count": _pass_count(output, "통계개념연결상태"),
        "catalog_pass_count": _pass_count(output, "공식통계표검색상태"),
        "metadata_pass_count": _pass_count(output, "KOSIS구조정보상태"),
        "hard_guard_pass_count": _pass_count(output, "필수조건검사상태"),
        "evidence_cell_pass_count": _pass_count(output, "근거좌표확정상태"),
        "official_fetch_pass_count": _pass_count(output, "공식값조회상태"),
        "strict_official_complete_count": sum(row["엄격공식판정완료"] == "Y" for row in output),
        "terminal_reason_counts": dict(sorted(Counter(_text(row["최종사유"]) for row in output).items())),
        "failure_stage_counts": dict(sorted(Counter(_text(row["최종실패단계"]) for row in output).items())),
    }
    if len(output) != len(scope):
        raise ValueError("DIRECT_VALUE_176_EVALUATION_COVERAGE_MISMATCH")
    return CoordinateEvaluation(tuple(output), summary)


def _evaluation_row(
    claim_id: str,
    base: Mapping[str, object],
    spec: Mapping[str, object],
    live: Mapping[str, object] | None,
    derived_count: int,
) -> dict[str, object]:
    events = _events(live)
    statuses = {str(event.get("stage")): str(event.get("status")) for event in events}
    verdict = _verdict(live)
    resolution = live.get("official_resolution") if isinstance(live, Mapping) else None
    resolution = resolution if isinstance(resolution, Mapping) else {}
    metadata_status = _metadata_status(resolution, statuses.get("KOSIS_METADATA"))
    evidence = verdict.get("evidence_cells") if isinstance(verdict, Mapping) else []
    values = verdict.get("evidence_values") if isinstance(verdict, Mapping) else []
    provenance = verdict.get("official_value_provenance") if isinstance(verdict, Mapping) else []
    readiness = _text(spec.get("readiness_status"))
    readiness_reasons = spec.get("readiness_reasons") or []
    terminal_status = _text(verdict.get("route_status")) if verdict else _text((live or {}).get("terminal_status"))
    terminal_reason = _text(verdict.get("reason_code")) if verdict else _text((live or {}).get("reason_code"))
    failure_stage = _failure_stage(readiness, readiness_reasons, events, terminal_status)
    return {
        "Claim번호": claim_id,
        "검증집합": _text(base.get("split_set")),
        "원문": _text(base.get("source_sentence")),
        "기존실패사유": _text(base.get("current_reason")),
        "검색지표": _text(spec.get("indicator")),
        "측정종류": _text(spec.get("measure_family")),
        "기사값": spec.get("value"),
        "단위": _text(spec.get("unit")),
        "기준시점": _text(spec.get("period")),
        "주기": _text(spec.get("frequency")),
        "지역": _text(spec.get("region")),
        "대상집단": _text(spec.get("population")),
        "차원조건JSON": json.dumps(spec.get("dimensions") or {}, ensure_ascii=False, sort_keys=True),
        "검색어JSON": json.dumps(spec.get("search_terms") or [], ensure_ascii=False),
        "명세준비상태": readiness,
        "명세차단사유": "|".join(map(str, readiness_reasons)),
        "파생Claim수": derived_count,
        "통계개념연결상태": statuses.get("SEMANTIC_MAPPING", "미도달"),
        "공식통계표검색상태": statuses.get("CATALOG_SEARCH", "미도달"),
        "KOSIS구조정보상태": metadata_status,
        "필수조건검사상태": statuses.get("HARD_GUARD", "미도달"),
        "후보의미비교상태": statuses.get("SEMANTIC_MATCH", "미도달"),
        "근거좌표확정상태": statuses.get("EVIDENCE_CELL", "미도달"),
        "공식값조회상태": statuses.get("OFFICIAL_VALUE_FETCH", "미도달"),
        "최종판정단계상태": statuses.get("VERDICT", "미도달"),
        "통계표후보수": resolution.get("candidate_count", 0),
        "근거좌표수": len(evidence or []),
        "공식값수": len(values or []),
        "공식근거수": len(provenance or []),
        "최종경로": terminal_status or ("PRE_VERIFICATION" if readiness == "PRE_VERIFICATION" else "미실행"),
        "최종판정": _text(verdict.get("verdict")) if verdict else "",
        "최종사유": terminal_reason or ("|".join(map(str, readiness_reasons)) if readiness == "PRE_VERIFICATION" else ""),
        "최종실패단계": failure_stage,
        "엄격공식판정완료": "Y" if readiness == "COORDINATE_READY" and _strict_complete(verdict) else "N",
        "공식근거URL": "|".join(_text(item.get("source_url")) for item in provenance or [] if isinstance(item, Mapping) and item.get("source_url")),
        "공식응답해시": "|".join(_text(item.get("content_hash")) for item in provenance or [] if isinstance(item, Mapping) and item.get("content_hash")),
    }



def _metadata_status(
    resolution: Mapping[str, object], explicit_status: str | None,
) -> str:
    if explicit_status:
        return explicit_status
    diagnostics = resolution.get("catalog_diagnostics")
    if not isinstance(diagnostics, Mapping):
        return "미도달"
    item_success = int(diagnostics.get("metadata_itm_succeeded") or 0)
    period_success = int(diagnostics.get("metadata_prd_succeeded") or 0)
    if item_success > 0 and period_success > 0:
        return "PASS"
    attempted = int(diagnostics.get("metadata_itm_attempted") or 0) + int(
        diagnostics.get("metadata_prd_attempted") or 0
    )
    return "HOLD" if attempted else "미도달"

def _events(live: Mapping[str, object] | None) -> list[Mapping[str, object]]:
    verdict = _verdict(live)
    trace = verdict.get("execution_trace") if isinstance(verdict, Mapping) else None
    events = trace.get("events") if isinstance(trace, Mapping) else None
    return [item for item in events or [] if isinstance(item, Mapping)]


def _verdict(live: Mapping[str, object] | None) -> Mapping[str, object]:
    resolution = live.get("official_resolution") if isinstance(live, Mapping) else None
    verdict = resolution.get("verdict") if isinstance(resolution, Mapping) else None
    return verdict if isinstance(verdict, Mapping) else {}


def _stage_score(row: Mapping[str, object]) -> tuple[int, int]:
    events = _events(row)
    indexes = [_STAGE_ORDER.index(str(event.get("stage"))) for event in events if str(event.get("stage")) in _STAGE_ORDER]
    return (max(indexes, default=-1), len(events))


def _failure_stage(readiness: str, readiness_reasons: object, events: list[Mapping[str, object]], terminal_status: str) -> str:
    if readiness == "PRE_VERIFICATION":
        return "사전 구조화"
    for event in events:
        if _text(event.get("status")) not in {"PASS", "AUTO"}:
            return _STAGE_KO.get(_text(event.get("stage")), _text(event.get("stage")))
    return "완료" if terminal_status == "AUTO" else "최종 판정"


def _strict_complete(verdict: Mapping[str, object]) -> bool:
    if verdict.get("route_status") != "AUTO" or verdict.get("verdict") not in {"MATCH", "MISMATCH"}:
        return False
    evidence = [item for item in verdict.get("evidence_cells") or [] if isinstance(item, Mapping)]
    provenance = [item for item in verdict.get("official_value_provenance") or [] if isinstance(item, Mapping)]
    evidence_keys = [_text(item.get("canonical_key")) for item in evidence]
    provenance_keys = [_text(item.get("evidence_key")) for item in provenance]
    if not evidence_keys or any(not key for key in evidence_keys + provenance_keys):
        return False
    if Counter(evidence_keys) != Counter(provenance_keys):
        return False
    return all(
        item.get("source") == "API"
        and item.get("source_url")
        and item.get("content_hash")
        and item.get("retrieved_at")
        and isinstance(item.get("publication"), Mapping)
        and item["publication"].get("status") == "VERIFIED"
        for item in provenance
    )


def _pass_count(rows: list[dict[str, object]], key: str) -> int:
    return sum(row[key] == "PASS" for row in rows)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
