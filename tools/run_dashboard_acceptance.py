"""Replay ledger-complete Claims through the exact Streamlit article boundary."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import asdict, fields, is_dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.canonical_pipeline import build_canonical_pipeline
from core.dashboard_acceptance import (
    DASHBOARD_LEDGER_HEADERS,
    DashboardAcceptanceResult,
    apply_acceptance_to_ledger,
    evaluate_dashboard_result,
    failed_dashboard_result,
    registry_article_dates,
    select_completed_cases,
    verify_dashboard_article,
)
from core.operational_error import OperationalStageError


def main(
    argv: Sequence[str] | None = None,
    *,
    runtime_builder: Callable[[], Any] | None = None,
) -> int:
    args = _parser().parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()) and not args.replace:
        raise SystemExit(f"OUTPUT_DIR_EXISTS:{args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_rows, ledger_headers = _read_csv(args.ledger_csv)
    cases = select_completed_cases(
        ledger_rows,
        registry_article_dates(args.registry_root),
    )
    if not cases:
        raise SystemExit("NO_COMPLETED_CLAIMS")
    code_version = args.code_version or _git_version()
    run_id = args.run_id or f"dashboard-acceptance-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    build = runtime_builder or _runtime_builder(args.live_budget_seconds)
    runtime = build()
    results: list[DashboardAcceptanceResult] = []
    raw_rows: list[dict[str, Any]] = []
    for case in cases:
        started = datetime.now(timezone.utc).isoformat()
        try:
            pipeline_result = verify_dashboard_article(
                runtime,
                case.article_text,
                article_published_at=case.article_published_at,
            )
            accepted = evaluate_dashboard_result(case, pipeline_result, run_id=run_id)
            raw_entries = _serialize(getattr(pipeline_result, "entries", []))
        except OperationalStageError as error:
            accepted = failed_dashboard_result(
                case,
                run_id=run_id,
                reason=f"{error.stage}_UNAVAILABLE",
            )
            raw_entries = [{"diagnostic_id": error.diagnostic_id, "reason_code": f"{error.stage}_UNAVAILABLE"}]
        except Exception as error:
            accepted = failed_dashboard_result(
                case,
                run_id=run_id,
                reason=f"PIPELINE_EXCEPTION:{type(error).__name__}",
            )
            raw_entries = [{"reason_code": f"PIPELINE_EXCEPTION:{type(error).__name__}"}]
        accepted = replace(accepted, recorded_at=started)
        results.append(accepted)
        raw_rows.append({
            "parent_claim_id": case.parent_claim_id,
            "article_id": case.article_id,
            "article_published_at": case.article_published_at.isoformat(),
            "article_text": case.article_text,
            "run_id": run_id,
            "code_version": code_version,
            "acceptance": asdict(accepted),
            "entries": raw_entries,
        })
    _write_results_csv(args.output_dir / "dashboard_acceptance_results.csv", results)
    _write_jsonl(args.output_dir / "dashboard_acceptance_results.jsonl", raw_rows)
    updated_rows = apply_acceptance_to_ledger(
        ledger_rows,
        results,
        code_version=code_version,
    )
    _write_ledger(
        args.ledger_csv,
        tuple(dict.fromkeys([*ledger_headers, *DASHBOARD_LEDGER_HEADERS])),
        updated_rows,
    )
    failures = Counter(item.failure_reason for item in results if item.failure_reason)
    summary = {
        "run_id": run_id,
        "code_version": code_version,
        "input_count": len(cases),
        "passed_count": sum(item.acceptance_status == "통과" for item in results),
        "failed_count": sum(item.acceptance_status == "실패" for item in results),
        "failure_reason_counts": dict(sorted(failures.items())),
        "ledger_path": str(args.ledger_csv.resolve()),
        "result_csv": str((args.output_dir / "dashboard_acceptance_results.csv").resolve()),
        "result_jsonl": str((args.output_dir / "dashboard_acceptance_results.jsonl").resolve()),
    }
    _write_json(args.output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def _runtime_builder(live_budget_seconds: float) -> Callable[[], Any]:
    def build() -> Any:
        settings = Settings()
        if not settings.kosis_api_key:
            raise RuntimeError("KOSIS_API_KEY_REQUIRED")
        return build_canonical_pipeline(
            settings,
            live_time_budget_seconds=live_budget_seconds,
        )
    return build


def _read_csv(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), tuple(reader.fieldnames or ())


def _write_results_csv(path: Path, results: list[DashboardAcceptanceResult]) -> None:
    headers = tuple(DashboardAcceptanceResult.__dataclass_fields__)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(asdict(item) for item in results)


def _write_ledger(path: Path, headers: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if hasattr(value, "__dict__"):
        return {str(key): _serialize(item) for key, item in vars(value).items()}
    return str(value)


def _git_version() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_csv", type=Path)
    parser.add_argument("registry_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--live-budget-seconds", type=float, default=45.0)
    parser.add_argument("--run-id")
    parser.add_argument("--code-version")
    parser.add_argument("--replace", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
