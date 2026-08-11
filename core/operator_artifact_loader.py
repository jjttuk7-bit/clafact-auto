"""Read-only loading of versioned internal-validation run artifacts."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OperatorRunArtifact:
    run_dir: Path
    report: dict[str, Any]
    results: list[dict[str, Any]]
    profile_queue: list[dict[str, Any]]
    review_summary: dict[str, Any]
    review_queues: dict[str, list[dict[str, Any]]]


def load_operator_run(run_dir: Path) -> OperatorRunArtifact:
    """Load only persisted artifacts; never alter verification results."""
    report = json.loads(
        _first_existing(
            run_dir, "coverage_and_e2e_report.json", "coverage_report.json"
        ).read_text(encoding="utf-8")
    )
    results = _read_jsonl(
        _first_existing(
            run_dir, "claim_verification_results.jsonl", "e2e_results.jsonl"
        )
    )
    priority_queue_path = run_dir / "profile_review_priority_queue.json"
    profile_queue = (
        json.loads(priority_queue_path.read_text(encoding="utf-8"))
        if priority_queue_path.is_file()
        else _read_jsonl(run_dir / "review_queues" / "profile.jsonl")
    )
    if not isinstance(report, dict) or not isinstance(profile_queue, list):
        raise ValueError("OPERATOR_ARTIFACT_INVALID")
    review_queues = _read_review_queues(run_dir / "review_queues")
    review_summary = _read_review_summary(run_dir / "review_queues", review_queues)
    return OperatorRunArtifact(run_dir, report, results, profile_queue, review_summary, review_queues)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("OPERATOR_ARTIFACT_INVALID")
    return rows


def _first_existing(run_dir: Path, *names: str) -> Path:
    for name in names:
        path = run_dir / name
        if path.is_file():
            return path
    raise FileNotFoundError(names[0])


def _read_review_queues(review_dir: Path) -> dict[str, list[dict[str, Any]]]:
    if not review_dir.is_dir():
        return {}
    return {path.stem: _read_jsonl(path) for path in sorted(review_dir.glob("*.jsonl"))}


def _read_review_summary(review_dir: Path, review_queues: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary_path = review_dir / "summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(summary, dict):
            return summary
        raise ValueError("OPERATOR_ARTIFACT_INVALID")
    return {"queue_counts": {name: len(rows) for name, rows in review_queues.items()}}
