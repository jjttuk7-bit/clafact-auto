"""Independently verify frozen CSV and JSONL Claim inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _csv_text(value: Any) -> str:
    return "" if value is None else str(value)


def verify_frozen_input(
    *,
    manifest_path: Path,
    csv_path: Path,
    jsonl_path: Path,
    expected_rows: int,
    claim_id_column: str,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path).resolve()
    csv_path = Path(csv_path).resolve()
    jsonl_path = Path(jsonl_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        csv_headers = list(reader.fieldnames or [])
        csv_rows = list(reader)

    jsonl_rows = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    jsonl_as_csv = [
        {header: _csv_text(record.get(header)) for header in csv_headers}
        for record in jsonl_rows
    ]

    manifest_headers = list(manifest.get("headers") or [])
    csv_hash_matches = _sha256(csv_path) == str(manifest["outputs"]["csv"]["sha256"]).upper()
    jsonl_hash_matches = _sha256(jsonl_path) == str(manifest["outputs"]["jsonl"]["sha256"]).upper()
    headers_match = csv_headers == manifest_headers
    jsonl_headers_match = all(list(row) == manifest_headers for row in jsonl_rows)
    rows_equal = csv_rows == jsonl_as_csv

    claim_ids = [str(row.get(claim_id_column, "")).strip() for row in csv_rows]
    missing_count = sum(not claim_id for claim_id in claim_ids)
    counts = Counter(claim_id for claim_id in claim_ids if claim_id)
    duplicate_ids = sorted(claim_id for claim_id, count in counts.items() if count > 1)
    duplicate_count = sum(count - 1 for count in counts.values() if count > 1)
    unique_count = len(counts)

    checks = {
        "expected_input_count": len(csv_rows) == expected_rows,
        "manifest_input_count": manifest.get("row_count") == expected_rows,
        "jsonl_input_count": len(jsonl_rows) == expected_rows,
        "manifest_column_count": manifest.get("column_count") == len(csv_headers),
        "csv_headers_match_manifest": headers_match,
        "jsonl_headers_match_manifest": jsonl_headers_match,
        "csv_hash_matches_manifest": csv_hash_matches,
        "jsonl_hash_matches_manifest": jsonl_hash_matches,
        "csv_jsonl_rows_equal": rows_equal,
        "claim_id_column_present": claim_id_column in csv_headers,
        "missing_claim_id_zero": missing_count == 0,
        "duplicate_claim_id_zero": duplicate_count == 0,
        "unique_claim_id_count_matches_input": unique_count == expected_rows,
    }
    issues = [name for name, passed in checks.items() if not passed]
    return {
        "version": 1,
        "verified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "PASS" if not issues else "FAIL",
        "expected_count": expected_rows,
        "input_count": len(csv_rows),
        "jsonl_count": len(jsonl_rows),
        "column_count": len(csv_headers),
        "unique_claim_id_count": unique_count,
        "missing_claim_id_count": missing_count,
        "duplicate_claim_id_count": duplicate_count,
        "duplicate_claim_ids": duplicate_ids,
        "csv_jsonl_rows_equal": rows_equal,
        "csv_hash_matches_manifest": csv_hash_matches,
        "jsonl_hash_matches_manifest": jsonl_hash_matches,
        "checks": checks,
        "issues": issues,
        "inputs": {
            "manifest": str(manifest_path),
            "csv": str(csv_path),
            "jsonl": str(jsonl_path),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=381)
    parser.add_argument("--claim-id-column", default="Claim번호")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = verify_frozen_input(
        manifest_path=args.manifest,
        csv_path=args.csv,
        jsonl_path=args.jsonl,
        expected_rows=args.expected_rows,
        claim_id_column=args.claim_id_column,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
