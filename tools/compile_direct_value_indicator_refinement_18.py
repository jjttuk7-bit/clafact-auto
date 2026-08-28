"""Merge the exact indicator-refinement 18-Claim run into the 230-row ledger."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


NEW_COLUMNS = [
    "지표구체화18재처리",
    "지표구체화18결과",
    "지표구체화18상위결과",
    "지표구체화18이동대상",
    "지표구체화18적용규칙",
    "지표구체화18수정지표",
    "지표구체화18수정시점",
    "지표구체화18수정주기",
    "지표구체화18수정지역",
    "지표구체화18최종상태",
    "지표구체화18최종사유",
    "지표구체화18실패단계",
    "지표구체화18후보수",
    "지표구체화18HardGuard통과수",
    "지표구체화18근거좌표수",
    "지표구체화18공식출처수",
    "지표구체화18공식판정",
    "지표구체화18공식값",
    "지표구체화18공식판정완료",
    "지표구체화18진단번호",
    "지표구체화18실행근거",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_csv", type=Path)
    parser.add_argument("manifest_json", type=Path)
    parser.add_argument("run_jsonl", type=Path)
    parser.add_argument("coverage_json", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("summary_json", type=Path)
    parser.add_argument("report_txt", type=Path)
    args = parser.parse_args()

    with args.ledger_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        original_columns = list(reader.fieldnames or [])
    manifest = json.loads(args.manifest_json.read_text(encoding="utf-8"))
    results = [json.loads(line) for line in args.run_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    coverage = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    decisions = {item["claim_id"]: item for item in manifest["decisions"]}
    run_by_id = {item["claim_id"]: item for item in results}

    if len(rows) != 230:
        raise ValueError(f"LEDGER_COUNT_MISMATCH:{len(rows)}:230")
    if len(decisions) != 18 or len(run_by_id) != manifest["run_count"]:
        raise ValueError("INDICATOR18_COVERAGE_MISMATCH")
    if set(run_by_id) != set(manifest["run_claim_ids"]):
        raise ValueError("INDICATOR18_RUN_ID_MISMATCH")

    seen: set[str] = set()
    for row in rows:
        claim_id = _text(row.get("자식Claim번호")) or _text(row.get("원본부모Claim번호"))
        decision = decisions.get(claim_id)
        if not decision:
            for column in NEW_COLUMNS:
                row.setdefault(column, "")
            continue
        seen.add(claim_id)
        row.update({
            "지표구체화18재처리": "Y",
            "지표구체화18결과": decision["result_code"],
            "지표구체화18상위결과": decision["top_level_result"],
            "지표구체화18이동대상": decision["target_tab"],
            "지표구체화18적용규칙": decision["applied_rule"],
            "지표구체화18실행근거": str(args.run_jsonl.resolve()) if claim_id in run_by_id else str(args.manifest_json.resolve()),
        })
        result = run_by_id.get(claim_id)
        if result is None:
            row.update(_non_run_fields(decision))
            continue
        claim = result["claim"]
        official = result.get("official_resolution") or {}
        verdict = official.get("verdict") or {}
        diagnostics = official.get("catalog_diagnostics") or {}
        evidence = verdict.get("evidence_cells") or []
        provenance = verdict.get("official_value_provenance") or []
        complete = _official_complete(result, verdict, evidence, provenance)
        row.update({
            "지표구체화18수정지표": _text(claim.get("indicator")),
            "지표구체화18수정시점": _text(claim.get("time")),
            "지표구체화18수정주기": _text(claim.get("frequency")),
            "지표구체화18수정지역": _text(claim.get("region")),
            "지표구체화18최종상태": _text(result.get("terminal_status")),
            "지표구체화18최종사유": _text(result.get("reason_code")),
            "지표구체화18실패단계": _failure_stage(_text(result.get("reason_code"))),
            "지표구체화18후보수": str(len(official.get("candidates") or [])),
            "지표구체화18HardGuard통과수": str(diagnostics.get("hard_guard_passed_count") or 0),
            "지표구체화18근거좌표수": str(len(evidence)),
            "지표구체화18공식출처수": str(len(provenance)),
            "지표구체화18공식판정": _text(verdict.get("verdict")),
            "지표구체화18공식값": _text(verdict.get("calculated_value")),
            "지표구체화18공식판정완료": "Y" if complete else "N",
            "지표구체화18진단번호": _text(result.get("diagnostic_id")),
        })

    if seen != set(decisions):
        raise ValueError(f"INDICATOR18_LEDGER_ID_MISMATCH:{sorted(set(decisions)-seen)}")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    columns = original_columns + [column for column in NEW_COLUMNS if column not in original_columns]
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    direct_reasons = Counter(item["reason_code"] for item in results)
    direct_complete = sum(
        1 for row in rows
        if row.get("지표구체화18재처리") == "Y" and row.get("지표구체화18공식판정완료") == "Y"
    )
    summary = {
        "source_ledger_count": len(rows),
        "scope_count": len(decisions),
        "decision_counts": dict(sorted(Counter(item["result_code"] for item in decisions.values()).items())),
        "direct_run_count": len(results),
        "direct_terminal_counts": dict(sorted(Counter(item["terminal_status"] for item in results).items())),
        "direct_reason_counts": dict(sorted(direct_reasons.items())),
        "direct_official_complete_count": direct_complete,
        "catalog_query_attempted": coverage["official_api_counts"]["catalog_query_attempted"],
        "metadata_item_attempted": coverage["official_api_counts"]["metadata_itm_attempted"],
        "metadata_period_attempted": coverage["official_api_counts"]["metadata_prd_attempted"],
        "manifest_sha256": manifest["manifest_sha256"],
        "input_registry": manifest["input_registry"],
        "run_results": str(args.run_jsonl.resolve()),
        "output_ledger": str(args.output_csv.resolve()),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_txt.parent.mkdir(parents=True, exist_ok=True)
    args.report_txt.write_text(_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


def _non_run_fields(decision: dict[str, object]) -> dict[str, str]:
    code = str(decision["result_code"])
    if code.startswith("EXCLUDE_"):
        status, stage = "검증대상제외", "CLAIM_RECLASSIFICATION"
    elif code == "MOVE_MULTI_PERIOD_SPLIT":
        status, stage = "복수Claim분리필요", "CLAIM_SPLIT"
    else:
        status, stage = "다른검증유형이동", "CLAIM_RECLASSIFICATION"
    return {
        "지표구체화18최종상태": status,
        "지표구체화18최종사유": str(decision["final_reason"]),
        "지표구체화18실패단계": stage,
        "지표구체화18후보수": "0",
        "지표구체화18HardGuard통과수": "0",
        "지표구체화18근거좌표수": "0",
        "지표구체화18공식출처수": "0",
        "지표구체화18공식판정완료": "N",
    }


def _official_complete(result: dict[str, object], verdict: dict[str, object], evidence: list[object], provenance: list[object]) -> bool:
    if result.get("terminal_status") != "AUTO" or verdict.get("route_status") != "AUTO":
        return False
    if verdict.get("verdict") not in {"MATCH", "MISMATCH"}:
        return False
    if not evidence or not provenance or len(evidence) != len(provenance):
        return False
    evidence_keys = Counter(str(item.get("canonical_key") or "") for item in evidence if isinstance(item, dict))
    provenance_keys = Counter(str(item.get("evidence_key") or "") for item in provenance if isinstance(item, dict))
    if "" in evidence_keys or "" in provenance_keys or evidence_keys != provenance_keys:
        return False
    return all(
        isinstance(item, dict)
        and item.get("source") == "API"
        and bool(item.get("source_url"))
        and bool(item.get("content_hash"))
        and bool(item.get("retrieved_at"))
        and isinstance(item.get("publication"), dict)
        and item["publication"].get("status") == "VERIFIED"
        for item in provenance
    )


def _failure_stage(reason: str) -> str:
    if reason == "KOSIS_CATALOG_UNAVAILABLE":
        return "KOSIS_CATALOG"
    if reason in {"NO_EVIDENCE_COORDINATE_CANDIDATE", "NO_HARD_GUARD_CANDIDATE"}:
        return "HARD_GUARD"
    return "VERDICT" if reason else ""


def _report(summary: dict[str, object]) -> str:
    decisions = summary["decision_counts"]
    reasons = summary["direct_reason_counts"]
    return f"""CLAFACT-AUTO 8번 직접값 - 지표 구체화 필요 18건 재처리 결과

1. 이번에 처리한 범위
- 전체 230건을 다시 돌리지 않았다.
- 이전 공식 재실행에서 '지표가 너무 넓거나 실제 측정대상과 다른 문제'로 멈춘 18건만 처리했다.

2. 18건을 원문 기준으로 다시 나눈 결과
- 공식통계 검증 제외: {decisions.get('EXCLUDE_POLICY_RATE', 0) + decisions.get('EXCLUDE_FORECAST', 0)}건
  · 정책 관세율 {decisions.get('EXCLUDE_POLICY_RATE', 0)}건, 미래 전망·예측 {decisions.get('EXCLUDE_FORECAST', 0)}건
- 비중·구성비 유형 이동: {decisions.get('MOVE_SHARE', 0)}건
- 여러 기간 Claim 분리 필요: {decisions.get('MOVE_MULTI_PERIOD_SPLIT', 0)}건
- 지표·시점·지역을 원문으로 교정해 직접값 공식 재조회: {decisions.get('KEEP_DIRECT_RECOVERED', 0)}건

3. 공통 규칙으로 고친 내용
- 수출액 같은 넓은 지표를 원문의 실제 측정값인 등록 대수, 수출량, 성장 기여도, 응답률, 생활물가 상승률, 경제성장률로 바꾼다.
- '올해 1~4월'은 기사 작성연도를 결합해 1월부터 4월까지의 누계기간으로 바꾼다.
- 국가 성장률 문장은 무역상대국이 아니라 성장 주체 국가를 지역으로 기록한다.
- 관세율·미래 전망은 관측된 KOSIS 통계값으로 보내지 않는다.
- 한 값이 두 연도에 동시에 걸리면 직접값 한 건으로 축약하지 않고 복수 Claim 분리 단계로 보낸다.

4. 직접값 {summary['direct_run_count']}건 실제 공식 API 재실행 결과
- 공식 판정 완료: {summary['direct_official_complete_count']}건
- KOSIS 표 검색 운영 오류: {reasons.get('KOSIS_CATALOG_UNAVAILABLE', 0)}건
- 표 후보와 구조정보는 찾았으나 근거 좌표가 완성되지 않음: {reasons.get('NO_EVIDENCE_COORDINATE_CANDIDATE', 0)}건
- 표 후보는 찾았으나 기간·지역·단위 조건을 모두 통과한 후보가 없음: {reasons.get('NO_HARD_GUARD_CANDIDATE', 0)}건
- 실제 공식 조회 기록: Catalog 검색 {summary['catalog_query_attempted']}회, 항목 구조정보 {summary['metadata_item_attempted']}회, 기간 구조정보 {summary['metadata_period_attempted']}회

5. 개선 전후의 의미
- 개선 전: 18건 모두 Claim의 실제 측정대상이 잘못되어 공식 검색 전에 '지표 구체화 필요'로 중단됐다.
- 개선 후: 12건은 검증 제외·유형 이동·복수기간 분리로 올바른 경로가 확정됐고, 6건은 수정된 직접값 Claim으로 공식 표 검색과 구조정보 조회까지 진입했다.
- 다만 6건 모두 공식값 판정까지는 가지 못했다. 다음 병목은 Claim 추출이 아니라 공식표 좌표 선택 5건과 Catalog 운영 오류 1건이다.
"""


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


if __name__ == "__main__":
    main()
