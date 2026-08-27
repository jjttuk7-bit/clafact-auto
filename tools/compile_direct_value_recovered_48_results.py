"""Compile the live 48-Claim run into the 230-row ledger and a Korean report."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.direct_value_recovered_results import (
    compile_recovered_official_results,
    merge_recovered_official_results,
    summarize_recovered_official_results,
)


REASON_KO = {
    "INDICATOR_REFINEMENT_REQUIRED": "지표 이름이 넓어서 공식 통계 항목을 하나로 좁히지 못함",
    "INDICATOR_UNIT_MEASURE_MISMATCH": "지표가 뜻하는 값의 종류와 기사 단위가 맞지 않음",
    "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE": "선택된 기사값이 원문 수치와 정확히 연결되지 않음",
    "NO_HARD_GUARD_CANDIDATE": "기사 조건을 모두 만족하는 공식 통계표 후보가 없음",
    "NO_EVIDENCE_COORDINATE_CANDIDATE": "통계표는 찾았지만 항목·기간·대상 좌표를 확정하지 못함",
    "DIRECT_VALUE_CHANGE_TARGET_MISCLASSIFIED": "직접 통계값이 아니라 증감 표현으로 다시 분류해야 함",
    "INDICATOR_MEASURE_FAMILY_AMBIGUOUS": "같은 지표명 아래 값의 종류가 여러 개라 하나로 확정하지 못함",
    "RELATIVE_TIME_UNRESOLVED": "지난달·올해 같은 상대 시점을 실제 기간으로 바꾸지 못함",
    "KOSIS_CATALOG_UNAVAILABLE": "실행 중 KOSIS 통계표 검색 요청이 실패함",
    "LOW_SEMANTIC_SCORE": "남은 후보가 기사 지표와 충분히 가깝지 않음",
    "FETCH_FAILED": "확정한 좌표의 공식값 조회가 실패함",
    "AS_OF_UNAVAILABLE": "기사 작성일 이전에 공개된 값인지 확인하지 못함",
    "PUBLICATION_FETCH_FAILED": "공식 공표 자료 조회가 실패함",
    "CONTEXT_TARGET_UNRESOLVED": "앞 문장의 대상이 필요한 표현이라 현재 문장만으로 대상을 확정할 수 없음",
    "TARGET_CHILD_UNRESOLVED": "복수 수치 분리 결과 중 검증 대상 자식을 하나로 확정하지 못함",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_csv", type=Path)
    parser.add_argument("pipeline_jsonl", type=Path)
    parser.add_argument("output_ledger_csv", type=Path)
    parser.add_argument("output_report_txt", type=Path)
    parser.add_argument("output_summary_json", type=Path)
    parser.add_argument("--expected-count", type=int, default=48)
    args = parser.parse_args()

    ledger = _read_csv(args.ledger_csv)
    pipeline = list(_read_jsonl(args.pipeline_jsonl))
    results = compile_recovered_official_results(
        ledger, pipeline, expected_count=args.expected_count
    )
    summary = summarize_recovered_official_results(results)
    summary["derived_child_count"] = len(pipeline)
    summary["input_ledger_sha256"] = sha256(args.ledger_csv.read_bytes()).hexdigest()
    summary["pipeline_results_sha256"] = sha256(args.pipeline_jsonl.read_bytes()).hexdigest()
    summary["pipeline_results"] = str(args.pipeline_jsonl.resolve())

    merged = merge_recovered_official_results(
        ledger, results, evidence_ref=str(args.pipeline_jsonl.resolve())
    )
    _validate(ledger, merged, results, args.expected_count)
    _write_csv(args.output_ledger_csv, merged)
    summary["output_ledger_csv"] = str(args.output_ledger_csv.resolve())
    summary["output_ledger_sha256"] = sha256(args.output_ledger_csv.read_bytes()).hexdigest()
    args.output_summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_report_txt.parent.mkdir(parents=True, exist_ok=True)
    args.output_report_txt.write_text(_report(summary), encoding="utf-8-sig")
    print(json.dumps({key: value for key, value in summary.items() if key != "records"}, ensure_ascii=False))


def _report(summary: dict[str, Any]) -> str:
    complete = int(summary["official_complete_count"])
    total = int(summary["input_parent_count"])
    reasons = summary["terminal_reason_counts"]
    stages = summary["failure_stage_counts"]
    lines = [
        "CLAFACT-AUTO 8번 직접값 — Claim 구조 복구 48건 공식 재실행 결과",
        "",
        "1. 무엇을 실행했는가",
        f"- 직접값 230건 가운데 원문 수치와 필수 정보가 복구된 48건만 실행했다.",
        "- 대시보드와 같은 통합 파이프라인으로 실제 KOSIS 검색·구조정보·값 조회와 공식 문서 확인을 수행했다.",
        f"- 원래 Claim {total}건이 복수 수치 분리 과정에서 자식 Claim {summary['derived_child_count']}건이 되었고, 원장의 검증 대상 수치와 일치하는 자식만 부모별 결과로 집계했다.",
        "",
        "2. 결과",
        f"- 공식 근거까지 판정 완료: {complete}건 / {total}건",
        f"- 일치: {summary['official_verdict_counts'].get('MATCH', 0)}건",
        f"- 불일치: {summary['official_verdict_counts'].get('MISMATCH', 0)}건",
        f"- 아직 판정 미완료: {total - complete}건",
        "- 완료 경로: KOSIS API에서 값을 조회하고 공식 작성기관 문서로 공표 시점을 확인한 혼합 경로 2건",
        "",
        "3. 완료 2건의 의미",
        "- 미국 대상 2024년 수출액 1건은 기사값과 공식값이 허용 오차 안에서 일치했다.",
        "- 2024년 전체 수출액 1건은 기사값과 공식값이 현재 허용 오차 밖이라 불일치로 판정됐다.",
        "- 이번 결과는 48건의 Claim 문장 복구가 곧 공식 판정 완료를 뜻하지 않는다는 점을 확인했다. 복구 뒤에도 통계표·항목·기간·대상 좌표가 확정되어야 한다.",
        "",
        "4. 미완료 원인(같은 원인끼리 묶음)",
    ]
    for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0])):
        if reason in {"WITHIN_TOLERANCE", "OUTSIDE_TOLERANCE"}:
            continue
        lines.append(f"- {REASON_KO.get(reason, reason)}: {count}건")
    lines.extend(["", "5. 문제가 발생한 단계"])
    for stage, count in sorted(stages.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {stage}: {count}건")
    lines.extend([
        "",
        "6. 실행 중 바로잡은 오류",
        "- 앞 문장의 대상이 필요한 ‘고용률도 …’ 문장을 전국 전체 고용률로 잘못 조회하던 문제를 발견했다.",
        "- 본문 문맥이 없으면 공식 조회 전에 문맥 보완 대상으로 멈추도록 수정했다.",
        "- 따라서 잘못된 불일치 1건을 최종 성과에서 제외했다.",
        "",
        "7. 다음 작업",
        "- 가장 큰 동일 원인인 ‘지표를 더 구체화해야 함’ 묶음부터 공통 세분화 규칙을 구현한다.",
        "- 그 묶음만 다시 실행해 공식 판정 완료 수가 몇 건 증가했는지 같은 원장에 누적 기록한다.",
        "- 전체 230건 또는 1,542건을 다시 실행하지 않는다.",
    ])
    return "\n".join(lines) + "\n"


def _validate(ledger: list[dict[str, str]], merged: list[dict[str, object]], results: list[Any], expected: int) -> None:
    if len(ledger) != 230 or len(merged) != 230:
        raise ValueError(f"RECOVERED_LEDGER_ROW_COUNT_MISMATCH:{len(ledger)}:{len(merged)}")
    executed = [row for row in merged if row.get("복구48공식재실행") == "Y"]
    if len(executed) != expected:
        raise ValueError(f"RECOVERED_EXECUTED_COUNT_MISMATCH:{len(executed)}:{expected}")
    ids = [row.parent_claim_id for row in results]
    if len(ids) != expected or len(set(ids)) != expected:
        raise ValueError("RECOVERED_RESULT_PARENT_ID_MISMATCH")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
