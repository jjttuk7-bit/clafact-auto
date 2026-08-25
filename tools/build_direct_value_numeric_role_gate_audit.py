"""Build the integrated numeric-role safety audit for 381 direct-value Claims."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


CSV_NAME = "CLAFACT_8번_직접값_381건_숫자역할오인차단.csv"
PATCH_JSONL_NAME = "CLAFACT_8번_직접값_381건_숫자역할오인차단_파이프라인보강.jsonl"
VERIFY_NAME = "CLAFACT_8번_직접값_381건_숫자역할오인차단_검증.json"
ADDED = [
    "숫자역할안전판정",
    "숫자역할차단사유",
    "숫자역할자동처리허용",
    "숫자역할검증표현",
    "숫자역할검증역할",
    "숫자역할파이프라인보강JSON",
]
_LINK_BLOCKS = {
    "TARGET_CONTEXT_ROLE_CONFLICT": (
        "PROTECTED_CONTEXT_BLOCKED",
        "TARGET_CONTEXT_ROLE_CONFLICT",
    ),
    "TARGET_NOT_FOUND_IN_SOURCE": (
        "TARGET_NOT_FOUND_BLOCKED",
        "TARGET_NOT_FOUND_IN_SOURCE",
    ),
    "TARGET_AMBIGUOUS_IN_SOURCE": (
        "AMBIGUOUS_TARGET_BLOCKED",
        "TARGET_AMBIGUOUS_IN_SOURCE",
    ),
}
_SAFE_ROLES = {"대상값", "증감값"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _file(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build_numeric_role_gate_artifacts(
    *,
    source_csv: Path,
    output_dir: Path,
    expected_rows: int,
) -> dict[str, Any]:
    source_csv = Path(source_csv).resolve()
    output_dir = Path(output_dir).resolve()
    with source_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = list(reader)
    required = {
        "Claim번호",
        "원문",
        "원문대상연결상태",
        "원문대상연결사유",
        "원문대상표현",
        "원문대상역할",
        "원문대상시작",
        "원문대상끝",
        "부호방향판정",
        "부호방향파이프라인보강JSON",
    }
    if not required.issubset(headers):
        raise ValueError("NUMERIC_ROLE_GATE_INPUT_COLUMNS_MISSING")
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, found {len(rows)}")

    output_rows: list[dict[str, str]] = []
    patch_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    seen: set[str] = set()
    issues: list[str] = []
    safe_count = 0
    blocked_count = 0
    for row in rows:
        claim_id = str(row["Claim번호"]).strip()
        if not claim_id:
            issues.append("EMPTY_CLAIM_ID")
        if claim_id in seen:
            issues.append(f"DUPLICATE_CLAIM_ID:{claim_id}")
        seen.add(claim_id)
        combined_patch = _json_object(
            row["부호방향파이프라인보강JSON"],
            f"NUMERIC_ROLE_PRIOR_PATCH_INVALID:{claim_id}",
        )
        status, reason, allowed, expression, role = _assess_row(row, combined_patch)
        if allowed:
            safe_count += 1
        else:
            blocked_count += 1
        status_counts[status] += 1
        reason_counts[reason] += 1
        combined_patch.update({
            "numeric_role_gate_status": status,
            "numeric_role_gate_reason_code": reason,
            "numeric_role_auto_allowed": allowed,
            "numeric_role_gate_version": "1.0",
        })
        patch_json = json.dumps(combined_patch, ensure_ascii=False, separators=(",", ":"))
        output_row = dict(row)
        output_row.update({
            "숫자역할안전판정": status,
            "숫자역할차단사유": reason,
            "숫자역할자동처리허용": "TRUE" if allowed else "FALSE",
            "숫자역할검증표현": expression,
            "숫자역할검증역할": role,
            "숫자역할파이프라인보강JSON": patch_json,
        })
        output_rows.append(output_row)
        patch_rows.append({
            "claim_id": claim_id,
            "source_sentence_sha256": hashlib.sha256(row["원문"].encode("utf-8")).hexdigest().upper(),
            "numeric_role_gate_status": status,
            "numeric_role_gate_reason_code": reason,
            "slot_enrichment_patch": combined_patch,
        })

    if len(seen) != len(rows):
        issues.append("CLAIM_ID_COUNT_MISMATCH")
    if safe_count + blocked_count != len(rows):
        issues.append("NUMERIC_ROLE_GATE_COUNT_MISMATCH")
    if any(not item["numeric_role_gate_reason_code"] for item in patch_rows):
        issues.append("NUMERIC_ROLE_GATE_REASON_MISSING")

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / CSV_NAME
    patch_path = output_dir / PATCH_JSONL_NAME
    verify_path = output_dir / VERIFY_NAME
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers + ADDED)
        writer.writeheader()
        writer.writerows(output_rows)
    with patch_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in patch_rows:
            handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    report: dict[str, Any] = {
        "version": 1,
        "verified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "PASS" if not issues else "FAIL",
        "input_count": len(rows),
        "output_count": len(output_rows),
        "unique_claim_id_count": len(seen),
        "safe_count": safe_count,
        "blocked_count": blocked_count,
        "status_counts": dict(status_counts),
        "reason_counts": dict(reason_counts),
        "issues": issues,
        "source": _file(source_csv),
        "outputs": {"csv": _file(csv_path), "patch_jsonl": _file(patch_path)},
    }
    verify_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report["verification_path"] = str(verify_path)
    return report


def _assess_row(
    row: dict[str, str],
    combined_patch: dict[str, Any],
) -> tuple[str, str, bool, str, str]:
    link_status = str(row["원문대상연결상태"]).strip()
    if link_status in _LINK_BLOCKS:
        status, reason = _LINK_BLOCKS[link_status]
        return status, reason, False, "", ""
    if link_status != "SOURCE_GROUNDED":
        return "ROLE_METADATA_INVALID_BLOCKED", "NUMERIC_ROLE_LINK_STATUS_INVALID", False, "", ""
    if row["부호방향판정"] == "TARGET_ROLE_REVIEW_REQUIRED":
        return (
            "LEVEL_ROLE_CONFLICT_BLOCKED",
            "TARGET_IS_LEVEL_NOT_CHANGE_AMOUNT",
            False,
            row["원문대상표현"],
            row["원문대상역할"],
        )

    expression = str(row["원문대상표현"])
    role = str(row["원문대상역할"])
    try:
        start = int(row["원문대상시작"])
        end = int(row["원문대상끝"])
    except (TypeError, ValueError):
        return "ROLE_METADATA_INVALID_BLOCKED", "NUMERIC_ROLE_SPAN_MISSING", False, expression, role
    source = row["원문"]
    if (
        not expression
        or role not in _SAFE_ROLES
        or start < 0
        or end <= start
        or source[start:end] != expression
        or combined_patch.get("target_link_status") != "SOURCE_GROUNDED"
        or combined_patch.get("target_numeric_expression") != expression
        or combined_patch.get("target_numeric_role") != role
    ):
        return "ROLE_METADATA_INVALID_BLOCKED", "NUMERIC_ROLE_METADATA_INVALID", False, expression, role
    return "SAFE_TARGET_ROLE", "NUMERIC_TARGET_ROLE_VERIFIED", True, expression, role


def _json_object(raw: str, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(reason) from error
    if not isinstance(value, dict):
        raise ValueError(reason)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=381)
    args = parser.parse_args()
    report = build_numeric_role_gate_artifacts(
        source_csv=args.source_csv,
        output_dir=args.output_dir,
        expected_rows=args.expected_rows,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
