"""Compile the complete 176-Claim coordinate-search evaluation CSV and report."""

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

from core.direct_value_coordinate_spec_evaluation import compile_coordinate_evaluation


DEFAULT_ARTIFACT = PROJECT_ROOT / "artifacts" / "direct_value_coordinate_spec_176_20260828"
DEFAULT_OUTPUT = PROJECT_ROOT / "deliverables" / "CLAFACT_AUTO_직접값176_전체좌표탐색_20260828"
CSV_NAME = "CLAFACT_AUTO_직접값176_단계별평가표.csv"
REPORT_NAME = "CLAFACT_AUTO_직접값176_결과보고서.txt"


def compile_artifacts(
    scope_json: Path,
    query_specs_jsonl: Path,
    live_results_jsonl: Path,
    output_dir: Path,
) -> dict[str, object]:
    scope_payload = json.loads(scope_json.read_text(encoding="utf-8"))
    scope = {
        str(item["claim_id"]): item
        for item in scope_payload.get("records", [])
        if isinstance(item, dict) and item.get("claim_id")
    }
    specs = {
        str(item["claim_id"]): item
        for item in _read_jsonl(query_specs_jsonl)
        if item.get("claim_id")
    }
    live_rows = _read_jsonl(live_results_jsonl)
    evaluation = compile_coordinate_evaluation(scope, specs, live_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / CSV_NAME
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evaluation.rows[0]))
        writer.writeheader()
        writer.writerows(evaluation.rows)
    summary = dict(evaluation.summary)
    summary.update({
        "evaluation_csv": CSV_NAME,
        "live_result_rows": len(live_rows),
        "scope_sha256": _sha256(scope_json),
        "query_specs_sha256": _sha256(query_specs_jsonl),
        "live_results_sha256": _sha256(live_results_jsonl),
        "evaluation_csv_sha256": _sha256(csv_path),
    })
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / REPORT_NAME).write_text(_report(summary), encoding="utf-8")
    return summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _report(summary: dict[str, object]) -> str:
    failures = summary.get("failure_stage_counts") or {}
    reasons = summary.get("terminal_reason_counts") or {}
    failure_lines = "\n".join(
        f"  - {name or '미분류'}: {count}건"
        for name, count in sorted(failures.items(), key=lambda item: (-int(item[1]), item[0]))
    )
    reason_lines = "\n".join(
        f"  - {name or '사유 없음'}: {count}건"
        for name, count in sorted(reasons.items(), key=lambda item: (-int(item[1]), item[0]))[:12]
    )
    return f"""CLAFACT-AUTO 직접값 미해결 176건 전체 좌표 탐색 결과

1. 무엇을 수행했나
- 전체 176건을 같은 KOSIS 검색 명세로 변환했다.
- 원문 수치·지표·단위·시점이 안전한 건만 실제 공식 API 좌표 탐색으로 보냈다.
- 각 Claim이 파이프라인의 어느 단계까지 갔는지를 단계별 평가표 한 행에 기록했다.

2. 단계별 결과
- 전체 대상: {summary.get('scope_count', 0)}건
- KOSIS 검색 명세 준비 완료: {summary.get('coordinate_ready_count', 0)}건
- KOSIS 이전 Claim 구조 보완 필요: {summary.get('preverification_count', 0)}건
- 통계 개념 연결 통과: {summary.get('semantic_pass_count', 0)}건
- 공식 통계표 검색 통과: {summary.get('catalog_pass_count', 0)}건
- KOSIS 구조정보 확인 통과: {summary.get('metadata_pass_count', 0)}건
- 필수 조건 검사 통과: {summary.get('hard_guard_pass_count', 0)}건
- 근거 좌표 확정 통과: {summary.get('evidence_cell_pass_count', 0)}건
- 공식값 조회 통과: {summary.get('official_fetch_pass_count', 0)}건
- 엄격한 공식 판정 완료: {summary.get('strict_official_complete_count', 0)}건

3. 현재 실패 단계
{failure_lines}

4. 현재 주요 사유
{reason_lines}

5. 결과 해석
- 이 결과는 일부 Claim을 통과시킨 수가 아니라, 176건 전체에서 공통 생성기와 좌표 탐색 엔진이 어디까지 작동했는지를 보여준다.
- 단계별 평가표를 기준으로 같은 실패 원인을 묶어 다음 공통 규칙을 구현하면, 새 뉴스에도 같은 개선이 적용된다.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, default=DEFAULT_ARTIFACT / "scope.json")
    parser.add_argument("--specs", type=Path, default=DEFAULT_ARTIFACT / "query_specs.jsonl")
    parser.add_argument("--live-results", type=Path, default=DEFAULT_ARTIFACT / "live_run" / "claim_verification_results_final.jsonl")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = compile_artifacts(args.scope, args.specs, args.live_results, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
