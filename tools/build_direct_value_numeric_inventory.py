"""Build a Claim-level inventory of all numeric source expressions."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.source_numeric_inventory import (
    digit_positions_not_covered,
    inventory_numeric_mentions,
)


CSV_NAME = "CLAFACT_8번_직접값_381건_원문수치목록.csv"
JSONL_NAME = "CLAFACT_8번_직접값_381건_원문수치목록.jsonl"
VERIFY_NAME = "CLAFACT_8번_직접값_381건_원문수치목록_검증.json"
ADDED_HEADERS = [
    "원문수치개수",
    "원문수치표현",
    "원문수치목록JSON",
    "미포함숫자위치JSON",
    "목록화상태",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def build_inventory(*, source_csv: Path, output_dir: Path, expected_rows: int) -> dict[str, Any]:
    source_csv = Path(source_csv).resolve()
    output_dir = Path(output_dir).resolve()
    with source_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        source_headers = list(reader.fieldnames or [])
        rows = list(reader)

    required = {"Claim번호", "원문"}
    if not required.issubset(source_headers):
        raise ValueError(f"missing required columns: {sorted(required - set(source_headers))}")
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, found {len(rows)}")
    claim_ids = [str(row.get("Claim번호") or "").strip() for row in rows]
    if any(not claim_id for claim_id in claim_ids):
        raise ValueError("missing Claim번호")
    if len(set(claim_ids)) != len(claim_ids):
        raise ValueError("duplicate Claim번호")

    output_rows: list[dict[str, str]] = []
    jsonl_rows: list[dict[str, Any]] = []
    uncovered_total = 0
    position_mismatch_count = 0
    claims_without_mentions: list[str] = []
    total_mentions = 0

    for row in rows:
        source_sentence = str(row.get("원문") or "")
        mentions = inventory_numeric_mentions(source_sentence)
        mention_dicts = [asdict(mention) for mention in mentions]
        uncovered = digit_positions_not_covered(source_sentence, mentions)
        mismatches = [
            mention.mention_id
            for mention in mentions
            if source_sentence[mention.start:mention.end] != mention.expression
        ]
        uncovered_total += len(uncovered)
        position_mismatch_count += len(mismatches)
        total_mentions += len(mentions)
        if not mentions:
            claims_without_mentions.append(row["Claim번호"])

        output_row = dict(row)
        output_row.update(
            {
                "원문수치개수": str(len(mentions)),
                "원문수치표현": " | ".join(mention.expression for mention in mentions),
                "원문수치목록JSON": json.dumps(mention_dicts, ensure_ascii=False, separators=(",", ":")),
                "미포함숫자위치JSON": json.dumps(uncovered, ensure_ascii=False, separators=(",", ":")),
                "목록화상태": "COMPLETE" if mentions else "NO_NUMERIC_MENTION",
            }
        )
        output_rows.append(output_row)
        jsonl_rows.append({**row, "원문수치목록": mention_dicts, "미포함숫자위치": uncovered})

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / CSV_NAME
    jsonl_path = output_dir / JSONL_NAME
    verify_path = output_dir / VERIFY_NAME
    output_headers = source_headers + ADDED_HEADERS

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_headers, extrasaction="raise")
        writer.writeheader()
        writer.writerows(output_rows)
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in jsonl_rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")

    issues: list[str] = []
    if uncovered_total:
        issues.append("UNCOVERED_DIGIT_POSITION")
    if position_mismatch_count:
        issues.append("SOURCE_POSITION_MISMATCH")
    result: dict[str, Any] = {
        "version": 1,
        "verified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "PASS" if not issues else "FAIL",
        "expected_count": expected_rows,
        "input_count": len(rows),
        "output_count": len(output_rows),
        "unique_claim_id_count": len(set(claim_ids)),
        "claim_with_inventory_count": len(output_rows),
        "claim_with_numeric_mentions_count": len(rows) - len(claims_without_mentions),
        "claims_without_numeric_mentions": claims_without_mentions,
        "total_numeric_mention_count": total_mentions,
        "uncovered_digit_count": uncovered_total,
        "position_mismatch_count": position_mismatch_count,
        "issues": issues,
        "source": _file_record(source_csv),
        "outputs": {"csv": _file_record(csv_path), "jsonl": _file_record(jsonl_path)},
    }
    verify_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["verification_path"] = str(verify_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=381)
    args = parser.parse_args()
    result = build_inventory(
        source_csv=args.source_csv,
        output_dir=args.output_dir,
        expected_rows=args.expected_rows,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
