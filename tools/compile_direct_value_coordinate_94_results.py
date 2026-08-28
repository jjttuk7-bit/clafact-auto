"""Compile the frozen 94-Claim before/after CSV, summary, and Korean report."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.direct_value_coordinate_94_comparison import compile_coordinate94_comparison
from core.direct_value_coordinate_spec_evaluation import compile_coordinate_evaluation


BASE = PROJECT_ROOT / "artifacts" / "direct_value_coordinate_spec_176_20260828"
ARTIFACT = PROJECT_ROOT / "artifacts" / "direct_value_coordinate_94_20260828"
BEFORE_DELIVERABLE = PROJECT_ROOT / "deliverables" / "CLAFACT_AUTO_직접값176_전체좌표탐색_20260828"
OUTPUT = PROJECT_ROOT / "deliverables" / "CLAFACT_AUTO_직접값94_공통좌표규칙_20260828"
AFTER_CSV = "CLAFACT_AUTO_직접값94_재실행후_단계별평가표.csv"
COMPARISON_CSV = "CLAFACT_AUTO_직접값94_공통좌표규칙_전후비교.csv"
REPORT_TXT = "CLAFACT_AUTO_직접값94_공통좌표규칙_결과보고서.txt"


def compile_artifacts(
    scope_json: Path,
    specs_jsonl: Path,
    before_csv: Path,
    classification_csv: Path,
    live_results_jsonl: Path,
    coverage_json: Path,
    output_dir: Path,
    *,
    expected_count: int = 94,
) -> dict[str, object]:
    classification = _read_csv(classification_csv)
    ids = {str(row.get("Claim번호") or "").strip() for row in classification}
    ids.discard("")
    if len(ids) != expected_count:
        raise ValueError(f"DIRECT_VALUE_94_CLASSIFICATION_COUNT:{len(ids)}")

    scope_payload = json.loads(scope_json.read_text(encoding="utf-8"))
    scope = {
        str(item["claim_id"]): item
        for item in scope_payload.get("records", [])
        if isinstance(item, dict) and str(item.get("claim_id")) in ids
    }
    specs = {
        str(item["claim_id"]): item
        for item in _read_jsonl(specs_jsonl)
        if str(item.get("claim_id")) in ids
    }
    live = _read_jsonl(live_results_jsonl)
    after = compile_coordinate_evaluation(scope, specs, live)
    before = [row for row in _read_csv(before_csv) if str(row.get("Claim번호")) in ids]
    comparison = compile_coordinate94_comparison(
        before,
        after.rows,
        classification,
        expected_count=expected_count,
    )
    coverage = json.loads(coverage_json.read_text(encoding="utf-8"))
    if coverage.get("input_registry_records") != expected_count or not coverage.get("input_coverage_complete"):
        raise ValueError("DIRECT_VALUE_94_LIVE_COVERAGE_INCOMPLETE")

    output_dir.mkdir(parents=True, exist_ok=True)
    after_path = output_dir / AFTER_CSV
    comparison_path = output_dir / COMPARISON_CSV
    _write_csv(after_path, list(after.rows))
    _write_csv(comparison_path, list(comparison.rows))

    summary = {
        **comparison.summary,
        "after_stage_summary": after.summary,
        "official_api_counts": coverage.get("official_api_counts") or {},
        "operational_failure_count": coverage.get("operational_failure_count"),
        "input_coverage_complete": coverage.get("input_coverage_complete"),
        "all_claims_terminal": coverage.get("all_claims_terminal"),
        "files": {
            "after_evaluation_csv": AFTER_CSV,
            "comparison_csv": COMPARISON_CSV,
            "report": REPORT_TXT,
        },
        "hashes": {
            "classification": _sha256(classification_csv),
            "live_results": _sha256(live_results_jsonl),
            "coverage": _sha256(coverage_json),
            "after_evaluation": _sha256(after_path),
            "comparison": _sha256(comparison_path),
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / REPORT_TXT).write_text(_report(summary), encoding="utf-8")
    return summary


def _report(summary: dict[str, object]) -> str:
    stage_counts = summary.get("after_failure_stage_counts") or {}
    reason_counts = summary.get("after_reason_counts") or {}
    movement = summary.get("movement_counts") or {}
    stages = "\n".join(f"  - {key}: {value}건" for key, value in sorted(stage_counts.items(), key=lambda item: (-int(item[1]), item[0])))
    reasons = "\n".join(f"  - {key}: {value}건" for key, value in sorted(reason_counts.items(), key=lambda item: (-int(item[1]), item[0])))
    return f"""CLAFACT-AUTO 직접값 좌표 병목 94건 공통 규칙 재실행 결과

1. 수행 범위
- 직접값 176건 중 이전 실행에서 모두 ‘필수 조건 검사’에 멈춘 동일 94건만 재실행했다.
- 전체 1,542건이나 다른 유형은 다시 실행하지 않았다.
- 적용한 공통 규칙은 같은 통화·같은 대상 안의 안전한 단위 배율 변환과 정확한 지역값 ‘국내→전국’이다.

2. 실제 공식 API 재실행 결과
- 입력·종료: {summary.get('scope_count', 0)}건 / 누락·중복 0건
- 엄격한 공식 판정 완료: {summary.get('strict_official_complete_count', 0)}건
- 이전 필수 조건 검사보다 뒤 단계로 이동: {summary.get('advanced_beyond_original_stage_count', 0)}건
- 단계 변화: {json.dumps(movement, ensure_ascii=False, sort_keys=True)}
- 운영 오류: {summary.get('operational_failure_count', 0)}건

3. 재실행 후 멈춘 단계
{stages}

4. 재실행 후 사유
{reasons}

5. 해석
- 이번 규칙은 94건을 개별 예외로 통과시킨 것이 아니라 모든 새 Claim에 적용되는 안전한 공통 정규화다.
- 다만 94건 대부분의 본질적 병목은 단위 배율 하나가 아니라, 잘못 구조화된 지표·대상과 여러 공식표 중 정확한 좌표를 하나로 고르는 문제로 확인됐다.
- 다음 개선은 남은 사유를 개별 Claim이 아니라 동일 원인 묶음으로 다시 처리해야 한다.
"""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("DIRECT_VALUE_94_EMPTY_OUTPUT")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, default=BASE / "scope.json")
    parser.add_argument("--specs", type=Path, default=BASE / "query_specs.jsonl")
    parser.add_argument("--before", type=Path, default=BEFORE_DELIVERABLE / "CLAFACT_AUTO_직접값176_단계별평가표.csv")
    parser.add_argument("--classification", type=Path, default=ARTIFACT / "classification.csv")
    parser.add_argument("--live-results", type=Path, default=ARTIFACT / "live_run_after_common_rules" / "claim_verification_results.jsonl")
    parser.add_argument("--coverage", type=Path, default=ARTIFACT / "live_run_after_common_rules" / "coverage_report.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    summary = compile_artifacts(args.scope, args.specs, args.before, args.classification, args.live_results, args.coverage, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
