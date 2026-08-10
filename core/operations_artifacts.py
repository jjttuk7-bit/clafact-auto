"""Read-only loaders for reproducible operations artifacts."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OperationsArtifacts:
    results: list[dict[str, Any]]
    coverage: dict[str, Any]
    review_queue: list[dict[str, Any]]


def load_operations_artifacts(results_path: Path, coverage_path: Path, review_queue_path: Path | None = None) -> OperationsArtifacts:
    """Load externally generated artifacts without mutating their contents."""
    results = _read_jsonl(results_path)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    if not isinstance(coverage, dict):
        raise ValueError("COVERAGE_REPORT_MUST_BE_OBJECT")
    return OperationsArtifacts(results, coverage, _read_jsonl(review_queue_path) if review_queue_path else [])


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("JSONL_ROWS_MUST_BE_OBJECTS")
    return rows
