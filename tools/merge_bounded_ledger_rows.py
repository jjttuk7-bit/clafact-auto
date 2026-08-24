"""Replace only explicitly selected rows in the 1,542-Claim progress ledger."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Sequence


def merge_selected_rows(
    master_rows: Sequence[dict[str, str]],
    rebuilt_rows: Sequence[dict[str, str]],
    selected_ids: set[str],
) -> list[dict[str, str]]:
    master = _index(master_rows)
    rebuilt = _index(rebuilt_rows)
    missing = sorted(selected_ids - master.keys() | selected_ids - rebuilt.keys())
    if missing:
        raise ValueError("SELECTED_CLAIM_NOT_FOUND:" + ",".join(missing))
    return [
        dict(rebuilt[row["Claim번호"]]) if row["Claim번호"] in selected_ids else dict(row)
        for row in master_rows
    ]


def _index(rows: Sequence[dict[str, str]]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        claim_id = str(row.get("Claim번호") or "")
        if not claim_id:
            raise ValueError("MISSING_CLAIM_ID")
        if claim_id in indexed:
            raise ValueError("DUPLICATE_CLAIM_ID:" + claim_id)
        indexed[claim_id] = row
    return indexed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master_csv", type=Path)
    parser.add_argument("rebuilt_csv", type=Path)
    parser.add_argument("selected_registry", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--expected-selected", type=int, required=True)
    args = parser.parse_args()

    master_headers, master_rows = _read_csv(args.master_csv)
    rebuilt_headers, rebuilt_rows = _read_csv(args.rebuilt_csv)
    selected_ids = _registry_claim_ids(args.selected_registry)
    if len(selected_ids) != args.expected_selected:
        parser.error(
            f"selected count mismatch: expected {args.expected_selected}, got {len(selected_ids)}"
        )
    merged = merge_selected_rows(master_rows, rebuilt_rows, selected_ids)
    headers = list(dict.fromkeys([*master_headers, *rebuilt_headers]))
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output_csv.with_suffix(args.output_csv.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)
    temporary.replace(args.output_csv)
    print(json.dumps({
        "rows": len(merged),
        "selected": len(selected_ids),
        "output": str(args.output_csv),
    }, ensure_ascii=False))


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        return list(reader.fieldnames or []), list(reader)


def _registry_claim_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        claim = payload.get("claim") if isinstance(payload, dict) else None
        claim_id = str(claim.get("claim_id") or "") if isinstance(claim, dict) else ""
        if not claim_id or claim_id in ids:
            raise ValueError(f"INVALID_SELECTED_IDENTITY:{line_number}")
        ids.add(claim_id)
    return ids


if __name__ == "__main__":
    main()
