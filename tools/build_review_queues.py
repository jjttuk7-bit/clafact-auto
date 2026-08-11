"""Build versioned review queue JSONL artifacts from immutable E2E results."""

import argparse
import json
from pathlib import Path

from core.review_queue_builder import build_review_queues
from schemas.claim_registry import ClaimRegistryRecord


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    results = _read_jsonl(args.results)
    records = {row.claim.claim_id: row for row in _read_registry(args.registry)}
    queues, summary = build_review_queues(results, records)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for queue_type, rows in queues.items():
        _write_jsonl(args.output_dir / f"{queue_type}.jsonl", rows)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_registry(path: Path) -> list[ClaimRegistryRecord]:
    return [ClaimRegistryRecord.model_validate(row) for row in _read_jsonl(path)]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
