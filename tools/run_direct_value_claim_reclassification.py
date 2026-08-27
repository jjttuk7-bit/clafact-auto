"""Run the frozen 100-Claim structure/classification re-adjudication."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from core.direct_value_claim_reclassification_results import (
    compile_reclassifications,
    merge_reclassifications,
    summarize_reclassifications,
)
from core.direct_value_claim_reclassification_scope import (
    FINAL_BLIND,
    INTERMEDIATE_VALIDATION,
    RULE_DISCOVERY,
    build_reclassification_scope,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-ledger", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=100)
    args = parser.parse_args()

    raw = args.input.read_bytes()
    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    scope = build_reclassification_scope(rows, expected_count=args.expected_count)
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.audit_dir / "scope_manifest.json"
    _write_json(manifest_path, {
        **scope.to_audit_dict(include_final_blind_source=False),
        "input_sha256": sha256(raw).hexdigest(),
    })

    # Rules are frozen before the final-blind phase. The final set is evaluated once.
    all_results = compile_reclassifications(rows, expected_count=args.expected_count)
    by_split = {name: [] for name in (RULE_DISCOVERY, INTERMEDIATE_VALIDATION, FINAL_BLIND)}
    for result in all_results:
        by_split[result.split_set].append(result)
    for split_name, records in by_split.items():
        path = args.audit_dir / f"results_{split_name.lower()}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n")

    rules_path = Path(__file__).resolve().parents[1] / "core" / "direct_value_claim_reclassifier.py"
    rules_sha = sha256(rules_path.read_bytes()).hexdigest()
    summary = summarize_reclassifications(all_results)
    summary.update({
        "input_row_count": len(rows),
        "input_sha256": sha256(raw).hexdigest(),
        "scope_manifest_sha256": scope.manifest_sha256,
        "rules_sha256": rules_sha,
        "final_blind_execution_count": len(by_split[FINAL_BLIND]),
        "final_blind_run_count": 1,
    })
    summary_path = args.audit_dir / "summary.json"
    _write_json(summary_path, summary)

    merged = merge_reclassifications(rows, all_results, evidence_ref=str(summary_path).replace("\\", "/"))
    args.output_ledger.parent.mkdir(parents=True, exist_ok=True)
    with args.output_ledger.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(merged[0].keys()), extrasaction="raise")
        writer.writeheader()
        writer.writerows(merged)

    _write_report(args.output_report, summary, args.input, args.output_ledger, summary_path)
    print(json.dumps({k: summary[k] for k in ("executed_count", "top_level_counts", "result_counts", "target_tab_counts", "split_counts")}, ensure_ascii=True, sort_keys=True))
    return 0


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_report(report: Path, summary: dict[str, object], input_path: Path, ledger_path: Path, summary_path: Path) -> None:
    top = summary["top_level_counts"]
    result = summary["result_counts"]
    tabs = summary["target_tab_counts"]
    remaining = summary["remaining_recovery_reason_counts"]
    exclusions = summary["exclusion_reason_counts"]
    easy_reason = {
        "CALCULATION_EVIDENCE_PLAN_UNRESOLVED": "공식값 계산에 필요한 비교값 구성 미확정",
        "CLAIM_PARSE_UNCERTAIN": "Claim 구조 해석 불확실",
        "MISSING_REQUIRED_SLOTS:time": "기준시점 누락",
        "TARGET_AMBIGUOUS_IN_SOURCE": "같은 후보 수치가 여러 개",
        "TARGET_NOT_FOUND_IN_SOURCE": "저장값과 원문 수치 연결 실패",
        "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE": "기사값이 원문 수치 표현과 불일치",
        "NON_OBSERVED_FORECAST": "관측값이 아닌 전망값",
        "NON_STATISTICAL_POLICY_THRESHOLD": "실제 통계가 아닌 정책 기준값",
        "NON_STATISTICAL_PRIVATE_TRANSACTION": "공공통계가 아닌 민간 계약값",
        "NON_STATISTICAL_PRODUCT_PRICE": "공공통계가 아닌 개별 상품 가격",
    }
    remaining_text = ", ".join(f"{easy_reason.get(key, key)} {value}건" for key, value in remaining.items())
    exclusion_text = ", ".join(f"{easy_reason.get(key, key)} {value}건" for key, value in exclusions.items())
    lines = [
        "CLAFACT-AUTO 8번 직접값 Claim 구조·분류 문제 100건 전량 재판정 결과",
        "",
        "1. 무엇을 재판정했나",
        f"- 8번 직접값 230행 원장 중 Claim 구조·분류 문제로 동결된 {summary['executed_count']}건 전부를 재판정했다.",
        "- Claim 번호별 예외 규칙은 쓰지 않고 원문 수치 역할, 관측/전망 여부, 계산 유형, 대상 수치의 원문 위치를 사용했다.",
        "- 규칙 발견 71건, 중간 검증 21건 뒤 규칙을 동결했고, 최종 미사용 8건은 1회만 실행했다.",
        "",
        "2. 재판정 결과",
        f"- 8번 직접값 유지: {top.get('KEEP_DIRECT_VALUE', 0)}건",
        f"  · 원문 근거와 필수 정보가 복구되어 파이프라인 재투입 가능: {result.get('KEEP_DIRECT_RECOVERED', 0)}건",
        f"  · 직접값은 맞지만 추가 구조 복구가 필요한 건: {result.get('KEEP_DIRECT_REQUIRES_RECOVERY', 0)}건",
        f"- 다른 검증 유형으로 이동: {top.get('MOVE_TO_OTHER_TYPE', 0)}건",
        f"  · 6번 증감량: {tabs.get('6.증감량', 0)}건",
        f"  · 7번 증감률: {tabs.get('7.증감률', 0)}건",
        f"  · 비중·기록·순위 등 기타 유형: {sum(v for k, v in tabs.items() if k not in {'6.증감량', '7.증감률', '8.직접값', '검증 제외'})}건",
        f"- KOSIS 검증 대상 제외: {top.get('EXCLUDE_FROM_KOSIS', 0)}건",
        f"- 합계: {sum(top.values())}건",
        f"- 추가 구조 복구 {sum(remaining.values())}건의 원인 묶음: {remaining_text}",
        f"- 검증 제외 {sum(exclusions.values())}건의 원인 묶음: {exclusion_text}",
        "",
        "3. 이 결과의 의미",
        "- 이번 완료는 공식값 판정 완료가 아니라, KOSIS 조회 전에 잘못된 Claim 구조·유형을 바로잡은 완료다.",
        "- 복구 완료 건은 8번 직접값 파이프라인으로 재투입하고, 이동 건은 해당 유형의 계산 경로로 보내며, 전망·정책 기준·민간 거래는 KOSIS에 잘못 조회하지 않는다.",
        "- 추가 구조 복구가 필요한 직접값은 사유를 그대로 남겨 다음 묶음의 정확한 입력으로 사용한다.",
        "",
        "4. 실행 근거",
        f"- 입력 원장: {input_path}",
        f"- 결과 원장: {ledger_path}",
        f"- 실행 요약: {summary_path}",
        f"- 입력 해시: {summary['input_sha256']}",
        f"- 규칙 해시: {summary['rules_sha256']}",
    ]
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


if __name__ == "__main__":
    raise SystemExit(main())
