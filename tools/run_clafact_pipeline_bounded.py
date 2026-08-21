"""Run canonical Registry verification in bounded workers with parent checkpoints."""

from __future__ import annotations

import argparse
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
from core.pipeline_run_reporting import build_run_report


WORKER_CLI = PROJECT_ROOT / "tools" / "run_clafact_pipeline.py"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--context-jsonl", type=Path)
    parser.add_argument("--worker-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--live-budget-seconds", type=float, default=30.0)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if args.max_workers < 1:
        parser.error("--max-workers must be at least one")

    source_rows = [
        json.loads(line)
        for line in args.registry_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows_by_index: dict[int, list[dict[str, Any]]] = {}
    if not args.no_resume:
        for index in range(len(source_rows)):
            checkpoint = load_checkpoint(args.output_dir, index)
            if checkpoint is not None:
                rows_by_index[index] = checkpoint

    pending_indices = [index for index in range(len(source_rows)) if index not in rows_by_index]
    with tempfile.TemporaryDirectory(prefix="clafact-bounded-") as temporary:
        temporary_root = Path(temporary)
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            pending = {
                executor.submit(
                    _run_one,
                    index,
                    source_rows[index],
                    temporary_root,
                    args.context_jsonl,
                    args.worker_timeout_seconds,
                    args.live_budget_seconds,
                ): index
                for index in pending_indices
            }
            for future in as_completed(pending):
                index = pending[future]
                rows = future.result()
                rows_by_index[index] = rows
                write_checkpoint(args.output_dir, index, rows)

    rows = [row for index in range(len(source_rows)) for row in rows_by_index[index]]
    _write_jsonl(args.output_dir / "claim_verification_results.jsonl", rows)
    report = build_run_report(rows, input_count=len(source_rows), registry_errors=[])
    report.update({
        "checkpoint_parent_count": len(rows_by_index),
        "resumed_parent_count": len(source_rows) - len(pending_indices),
    })
    _write_json(args.output_dir / "coverage_report.json", report)
    print(json.dumps({"output_dir": str(args.output_dir), **report}, ensure_ascii=False))


def write_checkpoint(output_dir: Path, index: int, rows: list[dict[str, Any]]) -> None:
    checkpoint_dir = output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    destination = checkpoint_dir / f"{index:05d}.jsonl"
    temporary = destination.with_suffix(".jsonl.tmp")
    _write_jsonl(temporary, rows)
    temporary.replace(destination)


def load_checkpoint(output_dir: Path, index: int) -> list[dict[str, Any]] | None:
    path = output_dir / "checkpoints" / f"{index:05d}.jsonl"
    if not path.is_file():
        return None
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return None
    return rows or None


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
    rows = [json.loads(line) for line in result_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows or [_failure_row(source_row, "WORKER_RESULT_EMPTY", result.stderr)]


def _failure_row(source_row: dict[str, Any], reason: str, diagnostic_text: str) -> dict[str, Any]:
    claim = source_row.get("claim") if isinstance(source_row.get("claim"), dict) else {}
    diagnostic_id = sha256(diagnostic_text.encode("utf-8")).hexdigest()[:12]
    return {
        "article_id": source_row.get("article_id"),
        "sentence_id": source_row.get("sentence_id"),
        "parent_claim_id": claim.get("claim_id"),
        "claim_id": claim.get("claim_id"),
        "source_sentence": claim.get("source_sentence"),
        "claim": claim,
        "recovery_action": "NO_RECOVERY",
        "admission_route": "KOSIS_PIPELINE_ELIGIBLE",
        "terminal_status": "HOLD",
        "reason_code": reason,
        "diagnostic_id": diagnostic_id,
        "official_resolution": None,
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
