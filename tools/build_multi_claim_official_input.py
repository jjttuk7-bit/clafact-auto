"""Materialize only official-search-eligible multi-Claim children as Registry JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.claim_registry_loader import load_claim_registry
from core.multi_claim_official_input import build_eligible_child_registry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-registry", type=Path, required=True)
    parser.add_argument("--group-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args(argv)

    loaded = load_claim_registry(args.parent_registry)
    if loaded.errors:
        parser.error(f"PARENT_REGISTRY_ERRORS:{len(loaded.errors)}")
    group_results = _load_jsonl(args.group_results)
    records = build_eligible_child_registry(loaded.records, group_results)
    if args.expected_count is not None and len(records) != args.expected_count:
        parser.error(
            f"ELIGIBLE_CHILD_COUNT_MISMATCH:{len(records)}:{args.expected_count}"
        )
    _write_registry(args.output, records)
    print(
        json.dumps(
            {"eligible_children": len(records), "output": str(args.output)},
            ensure_ascii=False,
        )
    )
    return 0


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"INVALID_GROUP_RESULT_ROW:{line_number}")
        rows.append(payload)
    return rows


def _write_registry(path: Path, records: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
            + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
