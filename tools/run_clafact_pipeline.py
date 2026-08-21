"""Run the canonical CLAFACT Registry pipeline through official engine v3."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.canonical_pipeline import build_canonical_pipeline
from core.claim_registry_loader import load_claim_registry
from core.operational_error import OperationalStageError, run_operational_stage
from core.pipeline_run_reporting import build_run_report, serialize_pipeline_entry
from core.unified_claim_pipeline import PipelineEntry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--context-jsonl", type=Path)
    parser.add_argument("--live-budget-seconds", type=float, default=30.0)
    args = parser.parse_args()
    settings = Settings()
    if not settings.kosis_api_key:
        parser.error("KOSIS_API_KEY is required")

    registry = load_claim_registry(args.registry_path)
    contexts = _load_context(args.context_jsonl)
    runtime = build_canonical_pipeline(
        settings,
        live_time_budget_seconds=args.live_budget_seconds,
    )
    rows: list[dict[str, Any]] = []
    for record in registry.records:
        try:
            entries = run_operational_stage(
                "PIPELINE",
                lambda record=record: runtime.verify_record(
                    record,
                    article_context=contexts.get(record.article_id),
                ),
            )
        except OperationalStageError as error:
            entries = [
                PipelineEntry(
                    record.claim.claim_id,
                    record.claim,
                    "NO_RECOVERY",
                    "KOSIS_PIPELINE_ELIGIBLE",
                    "HOLD",
                    f"{error.stage}_UNAVAILABLE",
                    None,
                    error.diagnostic_id,
                )
            ]
        rows.extend(serialize_pipeline_entry(record, entry) for entry in entries)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "claim_verification_results.jsonl", rows)
    report = build_run_report(
        rows,
        input_count=len(registry.records),
        registry_errors=list(registry.errors),
    )
    _write_json(args.output_dir / "coverage_report.json", report)
    print(json.dumps({"output_dir": str(args.output_dir), **report}, ensure_ascii=False))


def _load_context(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    contexts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row: Any = json.loads(line)
        article_id = str(row.get("article_id") or "").strip() if isinstance(row, dict) else ""
        text = (
            row.get("article_text")
            or row.get("body")
            or row.get("text")
            or row.get("context")
        ) if isinstance(row, dict) else None
        if article_id and isinstance(text, str) and text.strip():
            contexts[article_id] = text.strip()
    return contexts


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
