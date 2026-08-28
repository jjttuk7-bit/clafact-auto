from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.direct_value_type8_closeout import merge_type8_closeout
from core.direct_value_type8_failure_groups import classify_type8_result


DEFAULT_BASE = ROOT / "deliverables" / "CLAFACT_AUTO_8번_직접값_230건_지표구체화18재처리원장_20260828.csv"
DEFAULT_EVAL176 = ROOT / "deliverables" / "CLAFACT_AUTO_직접값176_전체좌표탐색_20260828" / "CLAFACT_AUTO_직접값176_단계별평가표.csv"
DEFAULT_LIVE176 = ROOT / "artifacts" / "direct_value_coordinate_spec_176_20260828" / "live_run" / "claim_verification_results_final.jsonl"
DEFAULT_EVAL94 = ROOT / "deliverables" / "CLAFACT_AUTO_직접값94_공통좌표규칙_20260828" / "CLAFACT_AUTO_직접값94_재실행후_단계별평가표.csv"
DEFAULT_LIVE94 = ROOT / "artifacts" / "direct_value_coordinate_94_20260828" / "claim_verification_results_compact.jsonl"
DEFAULT_OUTPUT = ROOT / "deliverables" / "CLAFACT_AUTO_8번_직접값_최종마감_20260828"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"TYPE8_JSONL_ROW_INVALID:{path}:{line_number}")
            rows.append(value)
    return rows


def _live_id(row: Mapping[str, object]) -> str:
    return str(row.get("claim_id") or row.get("parent_claim_id") or "").strip()


def _index(rows: Iterable[Mapping[str, object]], id_getter, error_code: str) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for row in rows:
        claim_id = str(id_getter(row) or "").strip()
        if not claim_id or claim_id in result:
            raise ValueError(error_code)
        result[claim_id] = row
    return result


def normalize_update(
    evaluation: Mapping[str, object],
    live: Mapping[str, object],
    *,
    source: str,
) -> dict[str, object]:
    resolution = live.get("official_resolution")
    if not isinstance(resolution, Mapping):
        resolution = {}
    verdict = resolution.get("verdict")
    if not isinstance(verdict, Mapping):
        verdict = {}
    official_values = verdict.get("evidence_values")
    evidence_cells = verdict.get("evidence_cells")
    provenance = verdict.get("official_value_provenance")
    return {
        "claim_id": str(evaluation.get("Claim번호") or "").strip(),
        "source": source,
        "terminal_status": str(evaluation.get("최종경로") or "").strip(),
        "reason_code": str(evaluation.get("최종사유") or "").strip(),
        "failure_stage": str(evaluation.get("최종실패단계") or "").strip(),
        "verdict": str(evaluation.get("최종판정") or verdict.get("verdict") or "").strip(),
        "official_values": official_values if isinstance(official_values, list) else [],
        "evidence_cells": evidence_cells if isinstance(evidence_cells, list) else [],
        "provenance": provenance if isinstance(provenance, list) else [],
    }


def _updates(
    evaluations: list[dict[str, str]],
    live_rows: list[dict[str, Any]],
    *,
    source: str,
    expected_count: int,
) -> list[dict[str, object]]:
    evaluation_index = _index(evaluations, lambda row: row.get("Claim번호"), "TYPE8_EVALUATION_ID_INVALID")
    live_index = _index(live_rows, _live_id, "TYPE8_LIVE_ID_INVALID")
    if len(evaluation_index) != expected_count or not set(live_index).issubset(evaluation_index):
        raise ValueError(f"TYPE8_RUN_COVERAGE_INVALID:{source}")
    return [normalize_update(row, live_index.get(claim_id, {}), source=source) for claim_id, row in evaluation_index.items()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: tuple[dict[str, Any], ...]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _report(summary: Mapping[str, object]) -> str:
    groups = Counter(summary.get("final_group_counts") or {})
    completed_sources = Counter(summary.get("completed_source_counts") or {})
    group_lines = "\n".join(f"  - {group}: {count}건" for group, count in groups.most_common())
    return (
        "CLAFACT-AUTO 8번 직접값 최종 마감 결과\n\n"
        "1. 무엇을 마감했는가\n"
        "- 1,542건을 다시 돌린 것이 아니다. 재분류가 끝난 8번 직접값 230건만 관리 대상으로 고정했다.\n"
        "- 230건 원장에 176건 전체 좌표 탐색 결과와 94건 공통 규칙 재실행 결과를 Claim 번호로 합쳤다.\n"
        "- 동일 Claim은 가장 최근 94건 재실행 결과가 이전 결과를 덮어쓰도록 했다.\n\n"
        "2. 최종 결과\n"
        f"- 최종 관리 대상: {summary['scope_count']}건\n"
        f"- 엄격한 공식 근거 판정 완료: {summary['strict_official_complete_count']}건\n"
        f"  · 일치: {summary['match_count']}건\n"
        f"  · 불일치: {summary['mismatch_count']}건\n"
        f"- 기존 원장 완료 10건 + 176건 실행 추가 {completed_sources.get('176_CANONICAL_RUN', 0)}건 + 94건 개선 재실행 추가 {completed_sources.get('94_COMMON_RULE_RERUN', 0)}건\n"
        f"- 공식 판정 미완료: {summary['scope_count'] - summary['strict_official_complete_count']}건\n\n"
        "3. 230건의 최종 문제 묶음\n"
        f"{group_lines}\n\n"
        "4. 완료로 센 기준\n"
        "- 기사값과 공식값의 일치/불일치 판정이 있어야 한다.\n"
        "- 사용한 공식 좌표와 공식 출처가 1:1로 연결되어야 한다.\n"
        "- 공식 URL, 응답 해시, 조회시각, 공표 확인이 모두 남아야 한다.\n"
        "- 위 조건이 하나라도 빠지면 완료 건수에 포함하지 않았다.\n\n"
        "5. 결론\n"
        "- 8번 직접값의 범위·최신 상태·근거·남은 문제가 하나의 230건 원장으로 확정됐다.\n"
        "- 그러나 공식 판정 자체는 17건만 완료됐으므로, 8번 유형의 자동 검증 개발이 전량 완료된 것은 아니다.\n"
        "- 남은 작업은 원장의 7개 문제 묶음별 공통 모듈 개선이며, 개별 Claim별 하드코딩으로 처리하지 않는다.\n"
    )


def compile_closeout(
    base_path: Path,
    eval176_path: Path,
    live176_path: Path,
    eval94_path: Path,
    live94_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    inputs = [base_path, eval176_path, live176_path, eval94_path, live94_path]
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    base = _read_csv(base_path)
    updates176 = _updates(_read_csv(eval176_path), _read_jsonl(live176_path), source="176_CANONICAL_RUN", expected_count=176)
    updates94 = _updates(_read_csv(eval94_path), _read_jsonl(live94_path), source="94_COMMON_RULE_RERUN", expected_count=94)
    result = merge_type8_closeout(base, updates176, updates94, expected_count=230)
    for row in result.rows:
        group, action = classify_type8_result(row)
        row["8번최종문제묶음"] = group
        row["8번다음조치"] = action

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "CLAFACT_AUTO_8번_직접값_230건_최종원장_20260828.csv"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "CLAFACT_AUTO_8번_직접값_최종마감_결과보고서.txt"
    _write_csv(ledger_path, result.rows)
    summary: dict[str, Any] = dict(result.summary)
    summary["final_group_counts"] = dict(Counter(row["8번최종문제묶음"] for row in result.rows))
    summary["completed_source_counts"] = dict(Counter(row["8번최종결과출처"] for row in result.rows if row["8번엄격공식판정완료"] == "Y"))
    summary["input_sha256"] = {str(path.relative_to(ROOT)): _sha256(path) for path in inputs}
    summary["output_ledger"] = str(ledger_path.relative_to(ROOT))
    summary["output_ledger_sha256"] = _sha256(ledger_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_report(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="8번 직접값 230건의 최신 실행 결과를 한 원장으로 확정합니다.")
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--eval176", type=Path, default=DEFAULT_EVAL176)
    parser.add_argument("--live176", type=Path, default=DEFAULT_LIVE176)
    parser.add_argument("--eval94", type=Path, default=DEFAULT_EVAL94)
    parser.add_argument("--live94", type=Path, default=DEFAULT_LIVE94)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = compile_closeout(args.base, args.eval176, args.live176, args.eval94, args.live94, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
