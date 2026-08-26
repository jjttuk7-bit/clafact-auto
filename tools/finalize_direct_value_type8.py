"""Compile the auditable type-8 direct-value ledger from final live runs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
from typing import Any

from core.direct_value_multi_claim_results import _is_official_verdict_complete
from core.direct_value_multi_claim_scope import load_direct_value_multi_claim_scope


FIELDS = (
    "행유형", "원본부모Claim번호", "자식Claim번호", "입력구분", "최종검증유형",
    "유형분류결과", "원문", "기사작성일", "대상수치표현", "지표", "기사값", "단위",
    "기준시점", "주기", "지역", "대상집단", "차원JSON", "계산방식", "조건JSON",
    "파싱상태", "공식조회진입경로", "최종상태", "최종사유코드", "실패단계",
    "실패원인_쉬운설명", "판정", "공식계산값", "공식좌표JSON", "공식출처JSON",
    "공식근거URL", "응답해시", "공표확인", "공식근거종류", "공식판정완료", "진단번호", "원본상세사유",
    "전체자식수", "8번직접값자식수", "다른유형자식수", "공식판정완료자식수",
    "실행결과파일",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("single_results", type=Path)
    parser.add_argument("multi_all_registry", type=Path)
    parser.add_argument("multi_type8_registry", type=Path)
    parser.add_argument("multi_results", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("output_summary", type=Path)
    args = parser.parse_args()

    source_rows = _csv_rows(args.source_csv)
    if len(source_rows) != 381:
        raise ValueError(f"TYPE8_SOURCE_COUNT_MISMATCH:{len(source_rows)}:381")
    source_by_id = {row["Claim번호"]: row for row in source_rows}
    if len(source_by_id) != 381:
        raise ValueError("TYPE8_SOURCE_PARENT_ID_NOT_UNIQUE")
    scope = load_direct_value_multi_claim_scope(
        args.source_csv,
        expected_parent_count=360,
        approved_external_limit=236,
    )
    single_ids = {case.parent_claim_id for case in scope.single_cases}
    grouping_ids = {case.parent_claim_id for case in scope.grouping_cases}

    single_results = _jsonl(args.single_results)
    multi_all = _jsonl(args.multi_all_registry)
    multi_type8 = _jsonl(args.multi_type8_registry)
    multi_results = _jsonl(args.multi_results)
    _expect_unique(single_results, "claim_id", 133, "SINGLE_RESULT")
    _expect_unique(multi_type8, "claim.claim_id", 197, "MULTI_TYPE8_INPUT")
    _expect_unique(multi_results, "claim_id", 197, "MULTI_RESULT")

    single_by_parent = {str(row["parent_claim_id"]): row for row in single_results}
    multi_parent_by_child = {
        str(row["claim"]["claim_id"]): str(
            (row.get("slot_enrichment") or {}).get("parent_claim_id") or ""
        )
        for row in multi_type8
    }
    all_children_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in multi_all:
        parent = str((row.get("slot_enrichment") or {}).get("parent_claim_id") or "")
        if parent:
            all_children_by_parent[parent].append(row)
    type8_children_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    result_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in multi_results:
        child_id = str(row["claim_id"])
        parent = multi_parent_by_child.get(child_id, "")
        if not parent:
            raise ValueError(f"MULTI_RESULT_PARENT_NOT_FOUND:{child_id}")
        type8_children_by_parent[parent].append(row)
        result_by_parent[parent].append(row)

    ledger: list[dict[str, Any]] = []
    for parent_id, source in source_by_id.items():
        if parent_id in single_ids:
            result = single_by_parent[parent_id]
            ledger.append(_result_row(
                result,
                parent_id=parent_id,
                row_type="부모겸단일결과",
                input_kind="단일 수치",
                source_row=source,
                result_file=args.single_results,
            ))
            continue
        if parent_id in grouping_ids:
            all_children = all_children_by_parent.get(parent_id, [])
            type8_results = result_by_parent.get(parent_id, [])
            complete = sum(_completion_kind(row) is not None for row in type8_results)
            reason_counts = Counter(str(row.get("reason_code") or "") for row in type8_results)
            ledger.append({
                **_blank(),
                "행유형": "복수문장부모요약",
                "원본부모Claim번호": parent_id,
                "입력구분": "복수 수치",
                "최종검증유형": "8번 직접값 자식만 실행",
                "유형분류결과": "복수 Claim 분리 후 자식별 결과 참조",
                "원문": source.get("원문", ""),
                "기사작성일": source.get("기사작성일", ""),
                "지표": source.get("지표", ""),
                "기사값": source.get("기사값", ""),
                "단위": source.get("단위", ""),
                "기준시점": source.get("기준시점", ""),
                "주기": source.get("주기", ""),
                "최종상태": "자식별 결과",
                "최종사유코드": json.dumps(reason_counts, ensure_ascii=False, sort_keys=True),
                "실패원인_쉬운설명": "한 문장을 자식 Claim으로 나눈 뒤 8번 직접값 자식만 공식 검증한 결과",
                "전체자식수": len(all_children),
                "8번직접값자식수": len(type8_results),
                "다른유형자식수": len(all_children) - len(type8_results),
                "공식판정완료자식수": complete,
                "실행결과파일": str(args.multi_results.resolve()),
            })
            continue
        ledger.append({
            **_blank(),
            "행유형": "입력차단부모",
            "원본부모Claim번호": parent_id,
            "입력구분": "비통계 숫자 역할 차단",
            "최종검증유형": "8번 직접값 제외",
            "유형분류결과": "공식조회 전 차단",
            "원문": source.get("원문", ""),
            "기사작성일": source.get("기사작성일", ""),
            "대상수치표현": source.get("숫자역할검증표현", ""),
            "지표": source.get("지표", ""),
            "기사값": source.get("기사값", ""),
            "단위": source.get("단위", ""),
            "기준시점": source.get("기준시점", ""),
            "주기": source.get("주기", ""),
            "파싱상태": "HUMAN_REVIEW",
            "최종상태": "공식조회 전 차단",
            "최종사유코드": source.get("숫자역할차단사유", ""),
            "실패단계": "Claim 수치 역할 확인",
            "실패원인_쉬운설명": "연령·기간·제품명 등 통계값이 아닌 숫자를 기사값으로 사용하지 않도록 차단",
            "실행결과파일": str(args.source_csv.resolve()),
        })

    for result in multi_results:
        parent_id = multi_parent_by_child[str(result["claim_id"])]
        ledger.append(_result_row(
            result,
            parent_id=parent_id,
            row_type="복수문장직접값자식결과",
            input_kind="복수 수치에서 분리",
            source_row=source_by_id[parent_id],
            result_file=args.multi_results,
        ))

    parent_rows = [row for row in ledger if row["행유형"] != "복수문장직접값자식결과"]
    if len(parent_rows) != 381:
        raise ValueError(f"TYPE8_PARENT_COVERAGE_MISMATCH:{len(parent_rows)}:381")
    if len(ledger) != 578:
        raise ValueError(f"TYPE8_LEDGER_ROW_COUNT_MISMATCH:{len(ledger)}:578")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ledger)

    detail_rows = [row for row in ledger if row["행유형"] in {"부모겸단일결과", "복수문장직접값자식결과"}]
    complete_rows = [row for row in detail_rows if row["공식판정완료"] == "Y"]
    moved = Counter(row["유형분류결과"] for row in detail_rows if row["유형분류결과"].startswith("다른 유형으로 이동"))
    reasons = Counter(row["최종사유코드"] for row in detail_rows if row["공식판정완료"] != "Y")
    summary = {
        "원본부모Claim수": 381,
        "입력차단부모수": sum(row["행유형"] == "입력차단부모" for row in parent_rows),
        "단일수치부모수": len(single_ids),
        "복수수치부모수": len(grouping_ids),
        "복수전체자식수": len(multi_all),
        "실행한8번상세결과수": len(detail_rows),
        "재분류후8번대상수": len(detail_rows) - sum(moved.values()),
        "전체공식근거완료수": len(complete_rows),
        "KOSIS_API완료수": sum(row["공식근거종류"] == "KOSIS_API" for row in complete_rows),
        "공식작성기관문서완료수": sum(row["공식근거종류"] == "OFFICIAL_DOCUMENT" for row in complete_rows),
        "일치수": sum(row["판정"] == "MATCH" for row in complete_rows),
        "불일치수": sum(row["판정"] == "MISMATCH" for row in complete_rows),
        "다른유형이동": dict(moved),
        "남은사유상위": dict(reasons.most_common(15)),
        "원장행수": len(ledger),
        "원장경로": str(args.output_csv.resolve()),
    }
    args.output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


def _result_row(
    result: dict[str, Any],
    *,
    parent_id: str,
    row_type: str,
    input_kind: str,
    source_row: dict[str, str],
    result_file: Path,
) -> dict[str, Any]:
    claim = result.get("claim") or {}
    resolution = result.get("official_resolution") or {}
    verdict = resolution.get("verdict") if isinstance(resolution, dict) else {}
    verdict = verdict if isinstance(verdict, dict) else {}
    evidence = verdict.get("evidence_cells") or []
    provenance = verdict.get("official_value_provenance") or []
    reason = str(result.get("reason_code") or "")
    move_type = {
        "RECLASSIFY_TO_DIFFERENCE": "다른 유형으로 이동: 6번 증감량",
        "RECLASSIFY_TO_GROWTH_RATE": "다른 유형으로 이동: 7번 증감률",
        "RECLASSIFY_TO_RECORD": "다른 유형으로 이동: 최고·최저 기록",
        "RECLASSIFY_TO_RANK": "다른 유형으로 이동: 순위",
        "RECLASSIFY_TO_SHARE": "다른 유형으로 이동: 비중·구성비",
    }.get(reason)
    completion_kind = _completion_kind(result)
    normalized_reason = _normalized_reason(reason)
    urls = sorted({str(item.get("source_url")) for item in provenance if item.get("source_url")})
    hashes = sorted({str(item.get("content_hash")) for item in provenance if item.get("content_hash")})
    publications = [item.get("publication") for item in provenance if isinstance(item.get("publication"), dict)]
    return {
        **_blank(),
        "행유형": row_type,
        "원본부모Claim번호": parent_id,
        "자식Claim번호": result.get("claim_id", ""),
        "입력구분": input_kind,
        "최종검증유형": "8번 직접값" if move_type is None else "8번 직접값 제외",
        "유형분류결과": move_type or "8번 직접값 유지",
        "원문": claim.get("source_sentence") or source_row.get("원문", ""),
        "기사작성일": source_row.get("기사작성일", ""),
        "대상수치표현": _target_expression(result),
        "지표": claim.get("indicator", ""),
        "기사값": claim.get("value", ""),
        "단위": claim.get("unit", ""),
        "기준시점": claim.get("time", ""),
        "주기": claim.get("frequency", ""),
        "지역": claim.get("region", ""),
        "대상집단": claim.get("population", ""),
        "차원JSON": _json(claim.get("dimension")),
        "계산방식": claim.get("calculation", ""),
        "조건JSON": _json(claim.get("condition")),
        "파싱상태": claim.get("parse_status", ""),
        "공식조회진입경로": result.get("admission_route", ""),
        "최종상태": result.get("terminal_status", ""),
        "최종사유코드": normalized_reason,
        "원본상세사유": reason if normalized_reason != reason else "",
        "실패단계": _failure_stage(result),
        "실패원인_쉬운설명": _easy_reason(reason),
        "판정": verdict.get("verdict", ""),
        "공식계산값": verdict.get("calculated_value", ""),
        "공식좌표JSON": _json(evidence),
        "공식출처JSON": _json(provenance),
        "공식근거URL": " | ".join(urls),
        "응답해시": " | ".join(hashes),
        "공표확인": "VERIFIED" if publications and all(p.get("status") == "VERIFIED" for p in publications) else "",
        "공식근거종류": completion_kind or "",
        "공식판정완료": "Y" if completion_kind is not None else "N",
        "진단번호": result.get("diagnostic_id", ""),
        "실행결과파일": str(result_file.resolve()),
    }


def _completion_kind(result: dict[str, Any]) -> str | None:
    if _is_official_verdict_complete(result):
        return "KOSIS_API"
    resolution = result.get("official_resolution")
    verdict = resolution.get("verdict") if isinstance(resolution, dict) else None
    if not isinstance(verdict, dict):
        return None
    if verdict.get("route_status") != "AUTO" or verdict.get("verdict") not in {"MATCH", "MISMATCH"}:
        return None
    provenance = verdict.get("official_value_provenance") or []
    if (
        verdict.get("evidence_values")
        and verdict.get("calculated_value") is not None
        and provenance
        and all(
            item.get("source") == "OFFICIAL_DOCUMENT"
            and item.get("source_url")
            and item.get("content_hash")
            and item.get("retrieved_at")
            and isinstance(item.get("publication"), dict)
            and item["publication"].get("status") == "VERIFIED"
            for item in provenance
        )
    ):
        return "OFFICIAL_DOCUMENT"
    return None


def _normalized_reason(reason: str) -> str:
    if not reason:
        return ""
    if all(character.isupper() or character.isdigit() or character in "_:.-" for character in reason):
        return reason
    return "CLAIM_PARSE_UNCERTAIN"
def _failure_stage(result: dict[str, Any]) -> str:
    for item in reversed(result.get("stage_results") or []):
        if item.get("status") not in {"PASS", "SKIPPED"}:
            return str(item.get("stage") or "")
    resolution = result.get("official_resolution") or {}
    verdict = resolution.get("verdict") if isinstance(resolution, dict) else {}
    trace = verdict.get("execution_trace") if isinstance(verdict, dict) else None
    events = trace.get("events") if isinstance(trace, dict) else []
    for item in reversed(events or []):
        if item.get("status") != "PASS":
            return str(item.get("stage") or "")
    return "VERDICT" if result.get("terminal_status") == "AUTO" else ""


def _easy_reason(reason: str) -> str:
    known = {
        "WITHIN_TOLERANCE": "기사값과 공식값이 허용오차 안에서 일치",
        "OUTSIDE_TOLERANCE": "기사값과 공식값이 허용오차 밖",
        "RECLASSIFY_TO_DIFFERENCE": "직접값이 아니라 두 기간 공식값의 차이를 계산해야 하는 증감량 주장",
        "RECLASSIFY_TO_GROWTH_RATE": "직접값이 아니라 두 기간 공식값으로 비율을 계산해야 하는 증감률 주장",
        "RECLASSIFY_TO_RECORD": "직접값이 아니라 과거 전체 기간과 비교해야 하는 기록 주장",
        "RECLASSIFY_TO_RANK": "직접값이 아니라 전체 지역·대상을 비교해야 하는 순위 주장",
        "RECLASSIFY_TO_SHARE": "직접값이 아니라 분자와 분모가 필요한 비중 주장",
        "TARGET_NOT_FOUND_IN_SOURCE": "구조화된 대상 수치가 뉴스 원문에서 확인되지 않음",
        "TARGET_AMBIGUOUS_IN_SOURCE": "같은 대상 수치가 원문에 여러 번 있어 자동 연결할 수 없음",
        "NO_HARD_GUARD_CANDIDATE": "기간·단위·지역 등 필수 조건을 모두 만족하는 공식표 후보가 없음",
        "NO_EVIDENCE_COORDINATE_CANDIDATE": "공식표는 찾았지만 기사 조건에 맞는 항목·지역·기간 좌표를 확정하지 못함",
        "AS_OF_UNAVAILABLE": "기사 작성일 기준 공표된 공식값인지 확인하지 못함",
        "KOSIS_CATALOG_UNAVAILABLE": "KOSIS 공식표 검색 요청이 일시적으로 실패함",
        "FETCH_FAILED": "확정한 좌표의 공식값 조회가 실패함",
        "GROUPING_AMBIGUOUS": "한 문장의 여러 수치를 독립 Claim으로 안전하게 나누지 못함",
    }
    return known.get(reason, reason or "공식 판정 완료")


def _target_expression(result: dict[str, Any]) -> str:
    lineage = result.get("lineage_record")
    return str(lineage.get("target_expression") or "") if isinstance(lineage, dict) else ""


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _expect_unique(rows: list[dict[str, Any]], dotted: str, expected: int, label: str) -> None:
    values = []
    for row in rows:
        value: Any = row
        for part in dotted.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        values.append(str(value or ""))
    if len(rows) != expected or len(set(values)) != expected or "" in values:
        raise ValueError(f"{label}_IDENTITY_MISMATCH:{len(rows)}:{len(set(values))}:{expected}")


def _blank() -> dict[str, Any]:
    return {field: "" for field in FIELDS}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if value not in (None, "") else ""


if __name__ == "__main__":
    main()
