"""Run the CLAFACT Registry pipeline in bounded, isolated external workers."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.bounded_process import run_bounded


WORKER_CLI = PROJECT_ROOT / "tools" / "run_clafact_pipeline.py"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--context-jsonl", type=Path)
    parser.add_argument("--worker-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--live-budget-seconds", type=float, default=10.0)
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args()
    if args.max_workers < 1:
        parser.error("--max-workers must be at least one")

    source_rows = [
        json.loads(line)
        for line in args.registry_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    with tempfile.TemporaryDirectory(prefix="clafact-bounded-") as temporary:
        temporary_root = Path(temporary)
        rows_by_index: dict[int, list[dict[str, Any]]] = {}
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            pending = {
                executor.submit(
                    _run_one,
                    index,
                    source_row,
                    temporary_root,
                    args.context_jsonl,
                    args.worker_timeout_seconds,
                    args.live_budget_seconds,
                ): index
                for index, source_row in enumerate(source_rows)
            }
            for future in as_completed(pending):
                index = pending[future]
                rows_by_index[index] = future.result()

    rows = [row for index in range(len(source_rows)) for row in rows_by_index[index]]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "claim_verification_results.jsonl", rows)
    report = _report(rows, len(source_rows))
    _write_json(args.output_dir / "coverage_report.json", report)
    print(json.dumps({"output_dir": str(args.output_dir), **report}, ensure_ascii=False))


def _run_one(
    index: int,
    source_row: dict[str, Any],
    temporary_root: Path,
    context_path: Path | None,
    timeout_seconds: float,
    live_budget_seconds: float,
) -> list[dict[str, Any]]:
    worker_root = temporary_root / f"worker-{index:05d}"
    worker_root.mkdir()
    input_path = worker_root / "input.jsonl"
    output_path = worker_root / "output"
    input_path.write_text(json.dumps(source_row, ensure_ascii=False) + "\n", encoding="utf-8")
    command = [
        sys.executable,
        str(WORKER_CLI),
        str(input_path),
        str(output_path),
        "--live-budget-seconds",
        str(live_budget_seconds),
    ]
    if context_path is not None:
        command.extend(["--context-jsonl", str(context_path.resolve())])
    result = run_bounded(
        command,
        timeout_seconds=timeout_seconds,
        cwd=str(PROJECT_ROOT),
        env=os.environ,
    )
    if result.timed_out:
        return [_failure_row(source_row, "EXTERNAL_PIPELINE_TIMEOUT", result.stderr)]
    if result.return_code != 0:
        return [_failure_row(source_row, "EXTERNAL_PIPELINE_FAILED", result.stderr)]
    result_path = output_path / "claim_verification_results.jsonl"
    if not result_path.exists():
        return [_failure_row(source_row, "WORKER_RESULT_MISSING", result.stderr)]
    return [
        json.loads(line)
        for line in result_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _failure_row(source_row: dict[str, Any], reason: str, diagnostic_text: str) -> dict[str, Any]:
    claim = source_row.get("claim") if isinstance(source_row.get("claim"), dict) else {}
    return {
        "article_id": source_row.get("article_id"),
        "sentence_id": source_row.get("sentence_id"),
        "parent_claim_id": claim.get("claim_id"),
        "claim_id": claim.get("claim_id"),
        "source_sentence": claim.get("source_sentence"),
        "recovery_action": "NO_RECOVERY",
        "admission_route": "STRUCTURAL_HOLD",
        "terminal_status": "HOLD",
        "reason_code": reason,
        "diagnostic_hash": sha256(diagnostic_text.encode("utf-8")).hexdigest(),
        "official_resolution": None,
    }


def _report(rows: list[dict[str, Any]], input_count: int) -> dict[str, Any]:
    terminal = [_terminal(row) for row in rows]
    return {
        "input_registry_records": input_count,
        "derived_claims": len(rows),
        "recovery_action_counts": dict(sorted(Counter(row["recovery_action"] for row in rows).items())),
        "admission_route_counts": dict(sorted(Counter(row["admission_route"] for row in rows).items())),
        "terminal_route_counts": dict(sorted(Counter(status for status, _ in terminal).items())),
        "terminal_reason_counts": dict(sorted(Counter(reason for _, reason in terminal if reason).items())),
        "official_resolution_count": sum(row.get("official_resolution") is not None for row in rows),
        "all_claims_terminal": all(status in {"AUTO", "HOLD"} for status, _ in terminal),
    }


def _terminal(row: dict[str, Any]) -> tuple[str, str | None]:
    resolution = row.get("official_resolution")
    if isinstance(resolution, dict) and isinstance(resolution.get("verdict"), dict):
        verdict = resolution["verdict"]
        return str(verdict.get("route_status") or "HOLD"), verdict.get("reason_code")
    return str(row.get("terminal_status") or "HOLD"), row.get("reason_code") or row.get("admission_route")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
