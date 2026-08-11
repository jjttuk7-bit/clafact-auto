"""Create an immutable derived Registry by applying audited slot-enrichment rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DerivedRegistryPaths:
    """Persisted paths for one source-preserving Registry merge."""

    registry_path: Path
    report_path: Path


def merge_enriched_registry(
    source_path: Path, enriched_path: Path, output_dir: Path
) -> DerivedRegistryPaths:
    """Apply enrichment by source key without ever overwriting the source Registry."""
    source_rows = _read_jsonl(source_path)
    enriched_rows = _read_jsonl(enriched_path)
    enriched_by_key = _unique_by_key(enriched_rows, "ENRICHED_SOURCE_KEY_DUPLICATE")
    source_keys = _unique_by_key(source_rows, "SOURCE_KEY_DUPLICATE")
    unknown_keys = set(enriched_by_key) - set(source_keys)
    if unknown_keys:
        raise ValueError("ENRICHED_SOURCE_KEY_NOT_FOUND")

    merged_rows = [
        enriched_by_key.get(_key(row), row)
        for row in source_rows
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    registry_path = output_dir / "derived_registry.jsonl"
    registry_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in merged_rows
        ),
        encoding="utf-8",
    )
    report_path = output_dir / "input_merge_report.json"
    report_path.write_text(
        json.dumps(
            {
                "source_records": len(source_rows),
                "enriched_records_applied": len(enriched_by_key),
                "unchanged_records": len(source_rows) - len(enriched_by_key),
                "source_registry": str(source_path),
                "enrichment_registry": str(enriched_path),
                "integrity_policy": "Source registry was not modified; this is a derived execution input.",
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return DerivedRegistryPaths(registry_path=registry_path, report_path=report_path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("REGISTRY_ROW_INVALID")
    return rows


def _unique_by_key(rows: list[dict[str, Any]], error_code: str) -> dict[tuple[str, str], dict[str, Any]]:
    indexed = {_key(row): row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(error_code)
    return indexed


def _key(row: dict[str, Any]) -> tuple[str, str]:
    article_id = row.get("article_id")
    sentence_id = row.get("sentence_id")
    if not isinstance(article_id, str) or not isinstance(sentence_id, str):
        raise ValueError("REGISTRY_SOURCE_KEY_REQUIRED")
    return article_id, sentence_id
