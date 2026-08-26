"""Compile primary and retry runs into auditable direct-value deliverables."""

from __future__ import annotations

from collections import Counter
import csv
from hashlib import sha256
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from core.direct_value_multi_claim_scope import DirectValueMultiClaimScope
from schemas.claim_registry import ClaimRegistryRecord


_OPERATIONAL_RETRY_REASONS = {
    "CLAIM_PARSE_UNAVAILABLE",
    "CLAIM_SPLIT_UNAVAILABLE",
    "KOSIS_CATALOG_UNAVAILABLE",
}


@dataclass(frozen=True, slots=True)
class CompiledMultiClaimResults:
    parent_rows: tuple[dict[str, Any], ...]
    child_rows: tuple[dict[str, Any], ...]
    structured_rows: tuple[dict[str, Any], ...]
    registry_rows: tuple[dict[str, Any], ...]
    execution_rows: tuple[dict[str, Any], ...]
    verification_rows: tuple[dict[str, Any], ...]
    report: dict[str, Any]


def compile_multi_claim_results(
    scope: DirectValueMultiClaimScope,
    primary_checkpoint: Path,
    retry_checkpoint: Path | None = None,
) -> CompiledMultiClaimResults:
    primary, primary_signature = _load_checkpoint(primary_checkpoint)
    expected = {case.parent_claim_id for case in scope.grouping_cases}
    if set(primary) != expected:
        raise ValueError(
            f"MULTI_CLAIM_RESULT_COVERAGE_MISMATCH:{len(primary)}:{len(expected)}"
        )
    retry: dict[str, dict[str, Any]] = {}
    retry_signature: str | None = None
    if retry_checkpoint is not None:
        retry, retry_signature = _load_checkpoint(retry_checkpoint)
        if not set(retry) <= expected:
            raise ValueError("MULTI_CLAIM_RETRY_SCOPE_MISMATCH")

    case_by_id = {case.parent_claim_id: case for case in scope.grouping_cases}
    for claim_id, result in primary.items():
        _validate_checkpoint_result(case_by_id[claim_id], result)
    for claim_id, result in retry.items():
        _validate_checkpoint_result(case_by_id[claim_id], result)
        initial = primary[claim_id]
        if (
            initial.get("status") == "PASS"
            or initial.get("reason_code") not in _OPERATIONAL_RETRY_REASONS
        ):
            raise ValueError("MULTI_CLAIM_RETRY_NOT_OPERATIONAL_FAILURE")
    normalized_primary = {
        claim_id: _normalize_grouping_result(result)
        for claim_id, result in primary.items()
    }
    normalized_retry = {
        claim_id: _normalize_grouping_result(result)
        for claim_id, result in retry.items()
    }
    effective = {
        claim_id: normalized_retry.get(claim_id, result)
        for claim_id, result in normalized_primary.items()
    }
    parent_rows: list[dict[str, Any]] = []
    child_rows: list[dict[str, Any]] = []
    structured_rows: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []
    execution_rows: list[dict[str, Any]] = []
    verification_rows: list[dict[str, Any]] = []

    for case in scope.parents:
        base = dict(case.source_row)
        if case.parent_claim_id not in expected:
            base.update({
                "복수Claim처리구분": "단일통계값_분리불필요",
                "발견통계수치수": len(case.expressions),
                "발견통계수치JSON": _json(case.expressions),
                "최초부모실행상태": "NOT_REQUIRED",
                "최초부모실행사유": "SINGLE_STATISTIC_PARENT",
                "재시도여부": "N",
                "재시도적용": "N",
                "부모실행상태": "NOT_REQUIRED",
                "부모실행사유": "SINGLE_STATISTIC_PARENT",
                "생성자식Claim수": 0,
                "자식Claim번호JSON": "[]",
                "자식최종상태요약JSON": "{}",
                "자식사유요약JSON": "{}",
                "공식판정완료자식수": 0,
                "운영오류자식수": 0,
                "실행서명": primary_signature,
            })
            parent_rows.append(base)
            continue

        initial = normalized_primary[case.parent_claim_id]
        result = effective[case.parent_claim_id]
        retried = case.parent_claim_id in retry
        children = list(result.get("children") or [])
        terminal_counts = Counter(str(child.get("terminal_status") or "") for child in children)
        reason_counts = Counter(str(child.get("reason_code") or "NONE") for child in children)
        base.update({
            "복수Claim처리구분": "복수통계값_구조화API실행",
            "발견통계수치수": len(case.expressions),
            "발견통계수치JSON": _json(case.expressions),
            "최초부모실행상태": initial.get("status"),
            "최초부모실행사유": initial.get("reason_code"),
            "재시도여부": "Y" if retried else "N",
            "재시도적용": "Y" if retried else "N",
            "부모실행상태": result.get("status"),
            "부모실행사유": result.get("reason_code"),
            "생성자식Claim수": len(children),
            "자식Claim번호JSON": _json([child.get("child_claim_id") for child in children]),
            "자식최종상태요약JSON": _json(dict(terminal_counts)),
            "자식사유요약JSON": _json(dict(reason_counts)),
            "자동경로도달자식수": terminal_counts.get("AUTO", 0),
            "공식판정완료자식수": sum(_is_official_verdict_complete(child) for child in children),
            "운영오류자식수": sum(bool(child.get("diagnostic_id")) for child in children),
            "실행서명": retry_signature if retried else primary_signature,
        })
        parent_rows.append(base)

        structured_rows.append({
            "parent_claim_id": case.parent_claim_id,
            "source_sentence": case.source_sentence,
            "expressions": list(case.expressions),
            "primary_result": _compact_parent_result(initial),
            "retry_result": _compact_parent_result(normalized_retry[case.parent_claim_id]) if retried else None,
            "effective_result_source": "retry" if retried else "primary",
            "retry_applied": retried,
            "primary_signature": primary_signature,
            "retry_signature": retry_signature if retried else None,
        })
        execution_rows.append({
            "부모Claim번호": case.parent_claim_id,
            "최초상태": initial.get("status"),
            "최초사유": initial.get("reason_code"),
            "재시도여부": "Y" if retried else "N",
            "재시도상태": normalized_retry.get(case.parent_claim_id, {}).get("status") if retried else None,
            "재시도사유": normalized_retry.get(case.parent_claim_id, {}).get("reason_code") if retried else None,
            "최종상태": result.get("status"),
            "최종사유": result.get("reason_code"),
            "발견수치수": len(case.expressions),
            "생성자식수": len(children),
            "진단번호JSON": _json([child.get("diagnostic_id") for child in children if child.get("diagnostic_id")]),
            "원문SHA256": result.get("source_sentence_sha256"),
            "실행서명": retry_signature if retried else primary_signature,
        })
        for ordinal, child in enumerate(children, start=1):
            child_rows.append(_child_csv_row(case, child, ordinal, retried))
            registry_rows.append(_registry_row(case, child, ordinal, retried))
            verification_rows.append(_verification_row(case, child, ordinal, retried))

    parent_status = Counter(
        str(result.get("status") or "") for result in effective.values()
    )
    parent_reason = Counter(
        str(result.get("reason_code") or "NONE") for result in effective.values()
    )
    child_terminal = Counter(row["최종상태"] for row in child_rows)
    child_reason = Counter(row["최종사유"] or "NONE" for row in child_rows)
    retry_recovered = sum(
        normalized_primary[claim_id].get("status") != "PASS"
        and normalized_retry[claim_id].get("status") == "PASS"
        for claim_id in retry
    )
    official_complete = sum(
        _is_official_verdict_complete(child)
        for result in effective.values()
        for child in result.get("children") or []
    )
    result_record_complete = all(
        result.get("status") == "PASS" or bool(result.get("reason_code"))
        for result in effective.values()
    )
    report = {
        "숫자역할안전부모수": len(scope.parents),
        "단일통계값부모수": len(scope.single_cases),
        "복수통계값실행부모수": len(scope.grouping_cases),
        "최초실행응답기록부모수": len(primary),
        "최초분리확정부모수": sum(result.get("status") == "PASS" for result in normalized_primary.values()),
        "재시도부모수": len(retry),
        "재시도회복부모수": retry_recovered,
        "최종실행응답기록부모수": len(effective),
        "최종분리확정부모수": parent_status.get("PASS", 0),
        "최종검토필요부모수": len(scope.grouping_cases) - parent_status.get("PASS", 0),
        "유효자식Claim수": len(child_rows),
        "자동경로도달자식수": child_terminal.get("AUTO", 0),
        "공식판정완료자식수": official_complete,
        "결과기록완전": result_record_complete,
        "보류자식수": child_terminal.get("HOLD", 0),
        "사람검토자식수": child_terminal.get("HUMAN_REVIEW", 0),
        "부모상태별건수": dict(parent_status),
        "부모사유별건수": dict(parent_reason),
        "자식상태별건수": dict(child_terminal),
        "자식사유별건수": dict(child_reason),
        "원본자료SHA256": scope.source_sha256,
        "최초실행서명": primary_signature,
        "재시도실행서명": retry_signature,
    }
    return CompiledMultiClaimResults(
        parent_rows=tuple(parent_rows),
        child_rows=tuple(child_rows),
        structured_rows=tuple(structured_rows),
        registry_rows=tuple(registry_rows),
        execution_rows=tuple(execution_rows),
        verification_rows=tuple(verification_rows),
        report=report,
    )


def write_multi_claim_deliverables(
    compiled: CompiledMultiClaimResults,
    output_dir: Path,
    *,
    date_tag: str,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"CLAFACT_AUTO_8번_1단계_복수Claim분리_{{name}}_{date_tag}"
    paths = {
        "parents_csv": output_dir / (stem.format(name="부모결과") + ".csv"),
        "children_csv": output_dir / (stem.format(name="자식결과") + ".csv"),
        "structured_jsonl": output_dir / (stem.format(name="구조화결과") + ".jsonl"),
        "registry_jsonl": output_dir / (stem.format(name="공식재입력") + ".jsonl"),
        "execution_csv": output_dir / (stem.format(name="실행이력") + ".csv"),
        "verification_csv": output_dir / (stem.format(name="검증이력") + ".csv"),
        "report_txt": output_dir / (stem.format(name="결과보고") + ".txt"),
        "checklist_json": output_dir / f"CLAFACT_AUTO_8번_체크리스트상태_1단계7완료_{date_tag}.json",
    }
    _write_csv(paths["parents_csv"], compiled.parent_rows)
    _write_csv(paths["children_csv"], compiled.child_rows)
    _write_jsonl(paths["structured_jsonl"], compiled.structured_rows)
    _write_jsonl(paths["registry_jsonl"], compiled.registry_rows)
    _write_csv(paths["execution_csv"], compiled.execution_rows)
    _write_csv(paths["verification_csv"], compiled.verification_rows)
    _atomic_text(paths["report_txt"], _easy_report(compiled.report), encoding="utf-8-sig")
    completion_basis = {
        "safe_parent_coverage_complete": len(compiled.parent_rows) == compiled.report["숫자역할안전부모수"],
        "grouping_parent_execution_complete": len(compiled.execution_rows) == compiled.report["복수통계값실행부모수"],
        "registry_validation_complete": len(compiled.registry_rows) == compiled.report["유효자식Claim수"],
        "unresolved_results_recorded": bool(compiled.report["결과기록완전"]),
    }
    checklist = {
        "phase_1_task_7": {
            "checked": all(completion_basis.values()),
            "title": "복수 통계값 문장 분리와 자식 Claim 재투입",
            "completion_basis": completion_basis,
            "report": compiled.report,
        }
    }
    _atomic_text(
        paths["checklist_json"],
        json.dumps(checklist, ensure_ascii=False, indent=2) + "\n",
    )
    return paths


def _load_checkpoint(path: Path) -> tuple[dict[str, dict[str, Any]], str]:
    rows: dict[str, dict[str, Any]] = {}
    signatures: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        claim_id = str(payload.get("parent_claim_id") or "")
        if not claim_id or claim_id in rows or payload.get("completed") is not True:
            raise ValueError("MULTI_CLAIM_CHECKPOINT_INVALID")
        rows[claim_id] = dict(payload.get("result") or {})
        signatures.add(str(payload.get("signature") or ""))
    if not signatures:
        return rows, ""
    if len(signatures) != 1:
        raise ValueError("MULTI_CLAIM_CHECKPOINT_SIGNATURE_INVALID")
    return rows, next(iter(signatures))


def _validate_checkpoint_result(case: Any, result: dict[str, Any]) -> None:
    if str(result.get("parent_claim_id") or "") != case.parent_claim_id:
        raise ValueError("MULTI_CLAIM_CHECKPOINT_PARENT_MISMATCH")
    expected_hash = sha256(case.source_sentence.encode("utf-8")).hexdigest().upper()
    if str(result.get("source_sentence_sha256") or "").upper() != expected_hash:
        raise ValueError("MULTI_CLAIM_CHECKPOINT_SOURCE_MISMATCH")
    if tuple(result.get("expressions") or ()) != tuple(case.expressions):
        raise ValueError("MULTI_CLAIM_CHECKPOINT_EXPRESSIONS_MISMATCH")


def _normalize_grouping_result(result: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(result)
    for child in result.get("children") or []:
        reason = str(child.get("reason_code") or "")
        if reason.startswith("GROUPING_"):
            normalized["status"] = "HUMAN_REVIEW"
            normalized["reason_code"] = reason
            break
    return normalized


def _is_official_verdict_complete(child: dict[str, Any]) -> bool:
    resolution = child.get("official_resolution")
    if not isinstance(resolution, dict):
        return False
    verdict = resolution.get("verdict")
    if not isinstance(verdict, dict):
        return False
    if verdict.get("route_status") != "AUTO" or verdict.get("verdict") not in {"MATCH", "MISMATCH"}:
        return False
    evidence = verdict.get("evidence_cells") or []
    provenance = verdict.get("official_value_provenance") or []
    if not evidence or not provenance or len(evidence) != len(provenance):
        return False
    evidence_keys = Counter(str(item.get("canonical_key") or "") for item in evidence)
    provenance_keys = Counter(str(item.get("evidence_key") or "") for item in provenance)
    if "" in evidence_keys or "" in provenance_keys or evidence_keys != provenance_keys:
        return False
    return all(
        item.get("source") == "API"
        and bool(item.get("source_url"))
        and bool(item.get("content_hash"))
        and bool(item.get("retrieved_at"))
        and isinstance(item.get("publication"), dict)
        and item["publication"].get("status") == "VERIFIED"
        for item in provenance
    )


def build_reinput_child_id(parent_claim_id: str, executed_child_id: str, ordinal: int) -> str:
    identity = f"{parent_claim_id}\n{executed_child_id}\n{ordinal}"
    digest = sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"claim_{digest}"


def compact_official_resolution(resolution: object) -> dict[str, Any]:
    if not isinstance(resolution, dict):
        return {}
    compact = dict(resolution)
    compact["candidates"] = [
        {
            key: value
            for key, value in candidate.items()
            if key != "dimension_member_codes"
        }
        for candidate in resolution.get("candidates") or []
        if isinstance(candidate, dict)
    ]
    return compact


def _compact_parent_result(result: dict[str, Any]) -> dict[str, Any]:
    compact = dict(result)
    children: list[dict[str, Any]] = []
    for child in result.get("children") or []:
        compact_child = dict(child)
        if isinstance(child.get("official_resolution"), dict):
            compact_child["official_resolution"] = compact_official_resolution(
                child["official_resolution"]
            )
        children.append(compact_child)
    compact["children"] = children
    return compact


def _child_csv_row(case: Any, child: dict[str, Any], ordinal: int, retried: bool) -> dict[str, Any]:
    claim = child.get("claim") or {}
    resolution = child.get("official_resolution") or {}
    verdict = resolution.get("verdict") or {}
    lineage = child.get("lineage_record") or {}
    evidence_cells = verdict.get("evidence_cells") or []
    provenance = verdict.get("official_value_provenance") or []
    executed_child_id = str(child.get("child_claim_id") or f"{case.parent_claim_id}_{ordinal}")
    reinput_child_id = build_reinput_child_id(case.parent_claim_id, executed_child_id, ordinal)
    return {
        "부모Claim번호": case.parent_claim_id,
        "자식순번": ordinal,
        "자식Claim번호": reinput_child_id,
        "실행자식Claim번호": executed_child_id,
        "대상수치표현": lineage.get("target_expression"),
        "원문": case.source_sentence,
        "지표": claim.get("indicator"),
        "기사값": claim.get("value"),
        "단위": claim.get("unit"),
        "기준시점": claim.get("time"),
        "주기": claim.get("frequency"),
        "지역": claim.get("region"),
        "대상집단": claim.get("population"),
        "차원JSON": _json(claim.get("dimension")),
        "비교조건JSON": _json(claim.get("comparison")),
        "계산방식": claim.get("calculation"),
        "조건JSON": _json(claim.get("condition")),
        "출처힌트": claim.get("source_hint"),
        "파싱상태": claim.get("parse_status"),
        "파싱사유": claim.get("parse_reason"),
        "복구작업": child.get("recovery_action"),
        "공식조회진입경로": child.get("admission_route"),
        "최종상태": child.get("terminal_status"),
        "최종사유": child.get("reason_code"),
        "진단번호": child.get("diagnostic_id"),
        "재시도결과": "Y" if retried else "N",
        "판정": verdict.get("verdict"),
        "판정경로": verdict.get("route_status"),
        "판정사유": verdict.get("reason_code"),
        "공식판정완료": "Y" if _is_official_verdict_complete(child) else "N",
        "계산값": verdict.get("calculated_value"),
        "근거좌표수": len(evidence_cells),
        "공식출처수": len(provenance),
        "개념JSON": _json(resolution.get("concept")),
        "근거좌표JSON": _json(evidence_cells),
        "공식출처JSON": _json(provenance),
        "12칸감사JSON": _json(child.get("slot_audit")),
        "단계별결과JSON": _json(child.get("stage_results")),
    }


def _registry_row(case: Any, child: dict[str, Any], ordinal: int, retried: bool) -> dict[str, Any]:
    executed_child_id = str(child.get("child_claim_id") or f"{case.parent_claim_id}_{ordinal}")
    reinput_child_id = build_reinput_child_id(case.parent_claim_id, executed_child_id, ordinal)
    claim = dict(child.get("claim") or {})
    claim["claim_id"] = reinput_child_id
    row = {
        "article_id": str(case.source_row.get("기사번호") or case.parent_claim_id.split("_")[0]),
        "sentence_id": reinput_child_id,
        "article_published_at": str(case.source_row.get("기사작성일") or "")[:10] or None,
        "source_ref": "direct_value_multi_claim_result_v1",
        "source_metadata": {
            "parent_claim_id": case.parent_claim_id,
            "retry_applied": "Y" if retried else "N",
            "target_expression": str((child.get("lineage_record") or {}).get("target_expression") or ""),
            "executed_child_claim_id": executed_child_id,
        },
        "claim": claim,
        "review_status": "UNREVIEWED",
        "slot_enrichment": {
            "stage": "TARGETED_MULTI_CLAIM_SPLIT",
            "parent_claim_id": case.parent_claim_id,
            "child_ordinal": ordinal,
            "lineage_record": child.get("lineage_record"),
            "slot_audit": child.get("slot_audit"),
        },
        "deterministic_slot_enrichment": None,
    }
    return ClaimRegistryRecord.model_validate(row).model_dump(mode="json")


def _verification_row(case: Any, child: dict[str, Any], ordinal: int, retried: bool) -> dict[str, Any]:
    resolution = child.get("official_resolution") or {}
    verdict = resolution.get("verdict") or {}
    audit = child.get("slot_audit") or {}
    executed_child_id = str(child.get("child_claim_id") or f"{case.parent_claim_id}_{ordinal}")
    reinput_child_id = build_reinput_child_id(case.parent_claim_id, executed_child_id, ordinal)
    return {
        "부모Claim번호": case.parent_claim_id,
        "자식순번": ordinal,
        "자식Claim번호": reinput_child_id,
        "실행자식Claim번호": executed_child_id,
        "재시도결과": "Y" if retried else "N",
        "12칸공식조회가능": audit.get("eligible_for_official_search"),
        "공식결과생성": "Y" if resolution else "N",
        "개념확정": (resolution.get("concept") or {}).get("status"),
        "후보수": len(resolution.get("candidates") or []),
        "근거좌표수": len(verdict.get("evidence_cells") or []),
        "공식출처수": len(verdict.get("official_value_provenance") or []),
        "판정": verdict.get("verdict"),
        "판정경로": verdict.get("route_status"),
        "판정사유": verdict.get("reason_code"),
        "최종상태": child.get("terminal_status"),
        "최종사유": child.get("reason_code"),
        "진단번호": child.get("diagnostic_id"),
    }


def _easy_report(report: dict[str, Any]) -> str:
    parent_reasons = report["부모사유별건수"]
    child_reasons = report["자식사유별건수"]
    lines = [
        "CLAFACT-AUTO 직접값 8번 · 복수 Claim 분리 결과",
        "",
        "1. 무엇을 했는가",
        f"- 숫자 역할이 안전한 부모 Claim {report['숫자역할안전부모수']}건을 확인했습니다.",
        f"- 수치가 하나인 {report['단일통계값부모수']}건은 분리하지 않고 보존했습니다.",
        f"- 수치가 둘 이상인 {report['복수통계값실행부모수']}건만 외부 구조화 API와 대시보드 동일 파이프라인으로 실행했습니다.",
        "",
        "2. 실행 결과",
        f"- 최초 외부 실행 응답 기록: {report['최초실행응답기록부모수']}건",
        f"- 최초 분리 확정: {report['최초분리확정부모수']}건",
        f"- 외부 오류 재시도: {report['재시도부모수']}건",
        f"- 재시도로 회복: {report['재시도회복부모수']}건",
        f"- 최종 외부 실행 응답 기록: {report['최종실행응답기록부모수']}건",
        f"- 최종 분리 확정: {report['최종분리확정부모수']}건",
        f"- 최종 검토 필요: {report['최종검토필요부모수']}건",
        f"- 최종 생성 자식 Claim: {report['유효자식Claim수']}건",
        f"- 자동 경로까지 도달한 자식: {report['자동경로도달자식수']}건",
        f"- KOSIS API 값·좌표·응답 hash·공표일이 모두 확인된 판정 완료: {report['공식판정완료자식수']}건",
        "",
        "3. 남은 문제",
    ]
    for reason, count in sorted(parent_reasons.items(), key=lambda item: (-item[1], item[0])):
        if reason != "NONE":
            lines.append(f"- 부모 단계 {reason}: {count}건")
    lines.extend(["", "4. 자식 Claim에서 많이 남은 문제"])
    for reason, count in sorted(child_reasons.items(), key=lambda item: (-item[1], item[0]))[:12]:
        lines.append(f"- {reason}: {count}건")
    lines.extend([
        "",
        "5. 이 결과의 의미",
        "- 특정 문장 하나를 고친 것이 아니라, 복수 수치 문장 전체에 같은 분리·검증 규칙을 적용했습니다.",
        "- 실행 완료와 공식 판정 완료를 구분해 기록했습니다.",
        "- 실패도 숨기지 않고 정확한 단계·사유·진단번호와 함께 기록했습니다.",
        "- 생성된 자식 Registry는 대시보드와 같은 통합 파이프라인에 다시 넣을 수 있습니다.",
        "",
    ])
    return "\n".join(lines)


def _write_csv(path: Path, rows: tuple[dict[str, Any], ...]) -> None:
    if not rows:
        raise ValueError(f"MULTI_CLAIM_CSV_EMPTY:{path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: tuple[dict[str, Any], ...]) -> None:
    _atomic_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _atomic_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding=encoding)
    temporary.replace(path)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
