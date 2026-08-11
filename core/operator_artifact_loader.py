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
    return OperatorRunArtifact(run_dir, report, results, profile_queue)


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
