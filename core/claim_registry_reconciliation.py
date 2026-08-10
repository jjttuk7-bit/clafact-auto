"""Compare Claim Registry versions without changing source records."""

from collections import Counter
import json
from pathlib import Path
from typing import Any


def compare_registry_artifacts(
    raw_path: Path, structured_path: Path, *, target_count: int | None = None
) -> dict[str, Any]:
    """Return an auditable key-level comparison of two Registry JSONL files."""
    raw_records = _read_jsonl(raw_path)
    structured_records = _read_jsonl(structured_path)
    raw_by_key = {_record_key(record): record for record in raw_records}
    structured_by_key = {_record_key(record): record for record in structured_records}
    raw_only_keys = sorted(raw_by_key.keys() - structured_by_key.keys())
    structured_only_keys = sorted(structured_by_key.keys() - raw_by_key.keys())
    raw_only_records = [
        _excluded_record(raw_by_key[(article_id, sentence_id)])
        for article_id, sentence_id in raw_only_keys
    ]
    return {
        "raw_count": len(raw_records),
        "structured_count": len(structured_records),
        "intersection_count": len(raw_by_key.keys() & structured_by_key.keys()),
        "raw_only_count": len(raw_only_keys),
        "structured_only_count": len(structured_only_keys),
        "target_count": target_count,
        "target_count_matches": target_count is None or len(structured_records) == target_count,
        "raw_only_route_counts": dict(
            sorted(Counter(record["route"] for record in raw_only_records).items())
        ),
        "raw_only_records": raw_only_records,
        "structured_only_records": [
            {"article_id": article_id, "sentence_id": sentence_id}
            for article_id, sentence_id in structured_only_keys
        ],
    }


def write_reconciliation_report(report: dict[str, Any], output_dir: Path) -> Path:
    """Write one UTF-8, human-reviewable reconciliation report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "reconciliation_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report_path


def _excluded_record(record: dict[str, Any]) -> dict[str, str | None]:
    metadata = record.get("source_metadata", {})
    result: dict[str, str | None] = {
        "article_id": str(record["article_id"]),
        "sentence_id": str(record["sentence_id"]),
        "route": metadata.get("route"),
    }
    for field in ("source_type", "claim_type", "reason"):
        if metadata.get(field) is not None:
            result[field] = metadata[field]
    return result


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _record_key(record: dict[str, Any]) -> tuple[str, str]:
    return str(record["article_id"]), str(record["sentence_id"])
