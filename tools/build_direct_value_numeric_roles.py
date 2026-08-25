"""Apply fail-closed numeric roles to the 381-row direct-value inventory."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.source_numeric_inventory import SourceNumericMention
from core.source_numeric_role_classifier import classify_numeric_roles


CSV_NAME = "CLAFACT_8번_직접값_381건_숫자역할분류.csv"
JSONL_NAME = "CLAFACT_8번_직접값_381건_숫자역할분류.jsonl"
VERIFY_NAME = "CLAFACT_8번_직접값_381건_숫자역할분류_검증.json"
ADDED = ["숫자역할개수", "숫자역할분포JSON", "숫자역할목록JSON", "자동대상표현", "자동대상역할", "대상연결상태", "자동대상제외사유"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _file(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def build_numeric_roles(*, source_csv: Path, output_dir: Path, expected_rows: int) -> dict[str, Any]:
    source_csv = Path(source_csv).resolve()
    output_dir = Path(output_dir).resolve()
    with source_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = list(reader)
    required = {"Claim번호", "원문", "기사값", "단위", "지표", "원문수치목록JSON"}
    if not required.issubset(headers):
        raise ValueError("missing numeric role input columns")
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, found {len(rows)}")

    output_rows: list[dict[str, str]] = []
    jsonl_rows: list[dict[str, Any]] = []
    role_counts: Counter[str] = Counter()
    target_status_counts: Counter[str] = Counter()
    missing_role = 0
    missing_exclusion = 0
    protected_conflicts = 0
    assignment_count = 0

    for row in rows:
        mention_payloads = json.loads(row["원문수치목록JSON"])
        mentions = [SourceNumericMention(**payload) for payload in mention_payloads]
        raw_value = str(row.get("기사값") or "").strip()
        try:
            claim_value = float(raw_value) if raw_value else None
        except ValueError:
            claim_value = None
        result = classify_numeric_roles(
            source_sentence=row["원문"],
            mentions=mentions,
            claim_value=claim_value,
            claim_unit=row.get("단위") or "",
            indicator=row.get("지표") or "",
        )
        assignments = [asdict(item) for item in result.assignments]
        assignment_count += len(assignments)
        role_counts.update(item["role"] for item in assignments)
        target_status_counts[result.target_status] += 1
        missing_role += sum(not item["role"] or not item["reason_code"] for item in assignments)
        missing_exclusion += sum(not item["auto_target_eligible"] and not item["exclusion_reason"] for item in assignments)
        protected_conflicts += sum(item["auto_target_eligible"] and item["role"] in {"기간", "기준연도", "기준값", "연령", "순위", "환산값", "제외"} for item in assignments)
        selected = [item for item in assignments if item["auto_target_eligible"]]
        role_distribution = dict(Counter(item["role"] for item in assignments))
        output_row = dict(row)
        output_row.update({
            "숫자역할개수": str(len(assignments)),
            "숫자역할분포JSON": json.dumps(role_distribution, ensure_ascii=False, separators=(",", ":")),
            "숫자역할목록JSON": json.dumps(assignments, ensure_ascii=False, separators=(",", ":")),
            "자동대상표현": " | ".join(item["expression"] for item in selected),
            "자동대상역할": " | ".join(item["role"] for item in selected),
            "대상연결상태": result.target_status,
            "자동대상제외사유": "" if selected else result.target_status,
        })
        output_rows.append(output_row)
        jsonl_rows.append({**row, "숫자역할목록": assignments, "대상연결상태": result.target_status})

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / CSV_NAME
    jsonl_path = output_dir / JSONL_NAME
    verify_path = output_dir / VERIFY_NAME
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers + ADDED, extrasaction="raise")
        writer.writeheader()
        writer.writerows(output_rows)
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in jsonl_rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")

    issues = []
    expected_assignment_count = sum(
        len(json.loads(row["원문수치목록JSON"])) for row in rows
    )
    if assignment_count != expected_assignment_count:
        issues.append("ASSIGNMENT_COUNT_MISMATCH")
    if missing_role:
        issues.append("MISSING_ROLE")
    if missing_exclusion:
        issues.append("MISSING_EXCLUSION_REASON")
    if protected_conflicts:
        issues.append("PROTECTED_ROLE_AUTO_TARGET_CONFLICT")
    report: dict[str, Any] = {
        "version": 1,
        "verified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "PASS" if not issues else "FAIL",
        "input_count": len(rows),
        "output_count": len(output_rows),
        "unique_claim_id_count": len({row["Claim번호"] for row in rows}),
        "assignment_count": assignment_count,
        "role_counts": dict(role_counts),
        "target_status_counts": dict(target_status_counts),
        "missing_role_count": missing_role,
        "missing_exclusion_reason_count": missing_exclusion,
        "protected_role_auto_target_conflict_count": protected_conflicts,
        "issues": issues,
        "source": _file(source_csv),
        "outputs": {"csv": _file(csv_path), "jsonl": _file(jsonl_path)},
    }
    verify_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["verification_path"] = str(verify_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=381)
    args = parser.parse_args()
    result = build_numeric_roles(source_csv=args.source_csv, output_dir=args.output_dir, expected_rows=args.expected_rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
