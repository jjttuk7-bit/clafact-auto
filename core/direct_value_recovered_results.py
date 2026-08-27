"""Compile parent-level official results for the recovered direct-value scope."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class RecoveredOfficialResult:
    parent_claim_id: str
    selected_claim_id: str
    child_count: int
    target_expression: str
    terminal_status: str
    reason_code: str
    verdict: str
    claim_value: float | None
    official_value: float | None
    official_complete: bool
    official_path: str
    failure_stage: str
    candidate_count: int
    evidence_count: int
    source_urls: tuple[str, ...]
    content_hashes: tuple[str, ...]
    publication_statuses: tuple[str, ...]


def compile_recovered_official_results(ledger_rows: Iterable[Mapping[str, object]], pipeline_rows: Iterable[Mapping[str, object]], *, expected_count: int = 48) -> list[RecoveredOfficialResult]:
    targets = {
        _text(row, "자식Claim번호") or _text(row, "원본부모Claim번호"): row
        for row in ledger_rows
        if _text(row, "Claim구조재판정결과") == "KEEP_DIRECT_RECOVERED"
    }
    if len(targets) != expected_count:
        raise ValueError(f"RECOVERED_OFFICIAL_TARGET_COUNT_MISMATCH:{len(targets)}:{expected_count}")
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in pipeline_rows:
        grouped[_text(row, "parent_claim_id")].append(row)
    if set(grouped) != set(targets):
        missing = sorted(set(targets) - set(grouped))
        extra = sorted(set(grouped) - set(targets))
        raise ValueError(f"RECOVERED_OFFICIAL_COVERAGE_MISMATCH:missing={len(missing)}:extra={len(extra)}")
    results = [_compile_parent(parent_id, targets[parent_id], grouped[parent_id]) for parent_id in sorted(targets)]
    if len(results) != expected_count:
        raise ValueError("RECOVERED_OFFICIAL_RESULT_COUNT_MISMATCH")
    return results


def summarize_recovered_official_results(results: Iterable[RecoveredOfficialResult]) -> dict[str, object]:
    rows = list(results)
    return {
        "input_parent_count": len(rows),
        "official_complete_count": sum(row.official_complete for row in rows),
        "terminal_status_counts": dict(sorted(Counter(row.terminal_status for row in rows).items())),
        "terminal_reason_counts": dict(sorted(Counter(row.reason_code for row in rows).items())),
        "failure_stage_counts": dict(sorted(Counter(row.failure_stage for row in rows if row.failure_stage).items())),
        "official_verdict_counts": dict(sorted(Counter(row.verdict for row in rows if row.official_complete).items())),
        "official_path_counts": dict(sorted(Counter(row.official_path for row in rows if row.official_complete).items())),
        "records": [asdict(row) for row in rows],
    }


def merge_recovered_official_results(ledger_rows: Iterable[Mapping[str, object]], results: Iterable[RecoveredOfficialResult], *, evidence_ref: str) -> list[dict[str, object]]:
    result_rows = list(results)
    by_id = {row.parent_claim_id: row for row in result_rows}
    if len(result_rows) != len(by_id):
        raise ValueError("RECOVERED_OFFICIAL_RESULT_NOT_UNIQUE")
    empty = {key: "" for key in (
        "복구48공식재실행", "복구48최종상태", "복구48최종사유", "복구48공식판정", "복구48공식값",
        "복구48공식판정완료", "복구48공식경로", "복구48실패단계", "복구48자식수", "복구48후보수",
        "복구48근거좌표수", "복구48출처URL", "복구48응답해시", "복구48공표상태", "복구48실행근거",
    )}
    merged: list[dict[str, object]] = []
    for original in ledger_rows:
        row = dict(original)
        claim_id = _text(row, "자식Claim번호") or _text(row, "원본부모Claim번호")
        result = by_id.get(claim_id)
        if result is None:
            for key, value in empty.items():
                row.setdefault(key, value)
        else:
            row.update({
                "복구48공식재실행": "Y", "복구48최종상태": result.terminal_status,
                "복구48최종사유": result.reason_code, "복구48공식판정": result.verdict,
                "복구48공식값": "" if result.official_value is None else result.official_value,
                "복구48공식판정완료": "Y" if result.official_complete else "N",
                "복구48공식경로": result.official_path, "복구48실패단계": result.failure_stage,
                "복구48자식수": result.child_count, "복구48후보수": result.candidate_count,
                "복구48근거좌표수": result.evidence_count, "복구48출처URL": " | ".join(result.source_urls),
                "복구48응답해시": " | ".join(result.content_hashes), "복구48공표상태": " | ".join(result.publication_statuses),
                "복구48실행근거": evidence_ref,
            })
        merged.append(row)
    return merged


def _compile_parent(parent_id: str, target: Mapping[str, object], children: list[Mapping[str, object]]) -> RecoveredOfficialResult:
    selected = _select_target_child(target, children)
    if selected is None:
        return RecoveredOfficialResult(parent_id, "", len(children), _text(target, "원문근거표현"), "HUMAN_REVIEW", "TARGET_CHILD_UNRESOLVED", "UNDETERMINED", _number(target.get("기사값")), None, False, "NONE", "CLAIM_SPLIT", 0, 0, (), (), ())
    resolution = selected.get("official_resolution")
    resolution = resolution if isinstance(resolution, Mapping) else {}
    verdict_payload = resolution.get("verdict")
    verdict_payload = verdict_payload if isinstance(verdict_payload, Mapping) else {}
    evidence = verdict_payload.get("evidence_cells")
    evidence = list(evidence) if isinstance(evidence, list) else []
    provenance = verdict_payload.get("official_value_provenance")
    provenance = list(provenance) if isinstance(provenance, list) else []
    official_path = _verified_official_path(evidence, provenance)
    terminal_status = _text(selected, "terminal_status")
    verdict = _text(verdict_payload, "verdict") or "UNDETERMINED"
    official_complete = terminal_status == "AUTO" and verdict in {"MATCH", "MISMATCH"} and official_path != "NONE"
    candidates = resolution.get("candidates")
    candidates = list(candidates) if isinstance(candidates, list) else []
    urls = tuple(sorted({str(item.get("source_url")) for item in provenance if isinstance(item, Mapping) and item.get("source_url")}))
    hashes = tuple(sorted({str(item.get("content_hash")) for item in provenance if isinstance(item, Mapping) and item.get("content_hash")}))
    publications = tuple(sorted({str(publication.get("status")) for item in provenance if isinstance(item, Mapping) and isinstance((publication := item.get("publication")), Mapping) and publication.get("status")}))
    reason = _text(selected, "reason_code") or _text(verdict_payload, "reason_code")
    claim = selected.get("claim")
    claim_value = _number(claim.get("value")) if isinstance(claim, Mapping) else _number(target.get("기사값"))
    return RecoveredOfficialResult(parent_id, _text(selected, "claim_id"), len(children), _text(target, "원문근거표현"), terminal_status, reason, verdict, claim_value, _number(verdict_payload.get("calculated_value")), official_complete, official_path if official_complete else "NONE", "" if official_complete else _failure_stage(verdict_payload, reason), len(candidates), len(evidence), urls, hashes, publications)


def _select_target_child(target: Mapping[str, object], children: list[Mapping[str, object]]) -> Mapping[str, object] | None:
    expression = _text(target, "원문근거표현")
    exact = []
    for row in children:
        lineage = row.get("lineage_record")
        if isinstance(lineage, Mapping) and _text(lineage, "target_expression") == expression:
            exact.append(row)
    if len(exact) == 1:
        return exact[0]
    target_value = _number(target.get("기사값"))
    numeric = []
    for row in children:
        claim = row.get("claim")
        if not isinstance(claim, Mapping):
            continue
        value = _number(claim.get("value"))
        if value is not None and target_value is not None and abs(value - target_value) <= max(1e-9, abs(target_value) * 1e-12):
            numeric.append(row)
    if len(numeric) == 1:
        return numeric[0]
    return children[0] if len(children) == 1 else None


def _verified_official_path(evidence: list[object], provenance: list[object]) -> str:
    keys = {str(item.get("canonical_key")) for item in evidence if isinstance(item, Mapping) and item.get("canonical_key")}
    if not keys:
        return "NONE"
    api_all: dict[str, bool] = {}
    api_publication_verified: dict[str, bool] = {}
    verified_documents = 0
    for item in provenance:
        if not isinstance(item, Mapping):
            continue
        publication = item.get("publication")
        if not item.get("source_url") or not item.get("content_hash") or not item.get("retrieved_at"):
            continue
        source = str(item.get("source") or "")
        evidence_key = str(item.get("evidence_key") or "")
        publication_verified = isinstance(publication, Mapping) and publication.get("status") == "VERIFIED"
        if source == "API" and evidence_key:
            api_all[evidence_key] = True
            api_publication_verified[evidence_key] = publication_verified
        elif source == "OFFICIAL_DOCUMENT" and publication_verified:
            verified_documents += 1
    if not all(api_all.get(key, False) for key in keys):
        return "NONE"
    if all(api_publication_verified.get(key, False) for key in keys):
        return "KOSIS_API"
    if verified_documents:
        return "KOSIS_API_VALUE_PLUS_OFFICIAL_DOCUMENT"
    return "NONE"


def _failure_stage(verdict: Mapping[str, object], reason: str) -> str:
    trace = verdict.get("execution_trace")
    events = trace.get("events") if isinstance(trace, Mapping) else None
    if isinstance(events, list):
        held = [item for item in events if isinstance(item, Mapping) and item.get("status") == "HOLD"]
        if held:
            return str(held[-1].get("stage") or "")
    mapping = {
        "NO_HARD_GUARD_CANDIDATE": "HARD_GUARD", "NO_EVIDENCE_COORDINATE_CANDIDATE": "EVIDENCE_CELL",
        "LOW_SEMANTIC_SCORE": "SEMANTIC_MATCH", "AMBIGUOUS_MARGIN": "SEMANTIC_MATCH",
        "FETCH_FAILED": "OFFICIAL_VALUE_FETCH", "AS_OF_UNAVAILABLE": "OFFICIAL_VALUE_FETCH",
        "PUBLICATION_FETCH_FAILED": "PUBLICATION_LOOKUP", "KOSIS_CATALOG_UNAVAILABLE": "CATALOG_SEARCH",
    }
    return mapping.get(reason, "CLAIM_PARSE")


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value).strip()


def _number(value: object) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
