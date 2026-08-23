"""Rebuild one auditable parent-Claim ledger from distributed result files."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.consolidated_claim_ledger import (
    build_child_parent_index,
    consolidate_rows,
    discover_updates,
    output_headers,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if (args.output_csv.exists() or args.summary_json.exists()) and not args.replace:
        parser.error("output exists; pass --replace to rebuild it")
    roots = list(dict.fromkeys(path.resolve() for path in args.results_roots))
    if not roots:
        parser.error("one or more --results-root values are required")
    for root in roots:
        if not root.is_dir():
            parser.error(f"results root not found: {root}")

    with args.master_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        master_headers = list(reader.fieldnames or [])
        master_rows = list(reader)
    if len(master_rows) != args.expected_count:
        parser.error(f"master count mismatch: expected {args.expected_count}, got {len(master_rows)}")
    master_ids = {str(row.get("Claim번호") or "") for row in master_rows}
    if len(master_ids) != len(master_rows) or "" in master_ids:
        parser.error("master Claim identities are missing or duplicated")

    child_parent = build_child_parent_index(roots, master_ids)
    updates = discover_updates(roots, master_ids, child_parent)
    try:
        rows = consolidate_rows(master_rows, updates)
    except ValueError as error:
        parser.error(str(error))
    headers = output_headers(master_headers)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_csv, headers, rows)
    digest = hashlib.sha256(args.output_csv.read_bytes()).hexdigest()
    updated = [row for row in rows if row.get("반영된결과수")]
    remaining_by_group = Counter(
        str(row.get("대표문제") or "UNCLASSIFIED")
        for row in rows
        if row.get("남은작업") != "완료"
    )
    summary = {
        "master_count": len(master_rows),
        "unique_claim_count": len(master_ids),
        "update_record_count": len(updates),
        "updated_claim_count": len(updated),
        "completed_claim_count": sum(row.get("남은작업") == "완료" for row in rows),
        "remaining_claim_count": sum(row.get("남은작업") != "완료" for row in rows),
        "remaining_by_primary_group": dict(sorted(remaining_by_group.items())),
        "child_parent_mapping_count": len(child_parent),
        "unmapped_result_count": 0,
        "output_sha256": digest,
        "results_roots": [str(root) for root in roots],
    }
    _write_json(args.summary_json, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def _write_csv(path: Path, headers: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("summary_json", type=Path)
    parser.add_argument("--results-root", dest="results_roots", action="append", type=Path, default=[])
    parser.add_argument("--expected-count", type=int, default=1542)
    parser.add_argument("--replace", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
