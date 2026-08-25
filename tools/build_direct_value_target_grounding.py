"""Build exact source-target grounding artifacts for 381 direct-value Claims."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from core.source_target_grounding import build_target_grounding


CSV_NAME = "CLAFACT_8번_직접값_381건_대상값원문연결.csv"
PATCH_JSONL_NAME = "CLAFACT_8번_직접값_381건_대상값원문연결_파이프라인보강.jsonl"
VERIFY_NAME = "CLAFACT_8번_직접값_381건_대상값원문연결_검증.json"
ADDED = [
    "원문대상연결상태",
    "원문대상연결사유",
    "원문대상표현",
    "원문대상MentionID",
    "원문대상역할",
    "원문대상시작",
    "원문대상끝",
    "파이프라인보강JSON",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _file(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build_target_grounding_artifacts(
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
        "원문수치목록JSON",
        "숫자역할목록JSON",
        "자동대상표현",
        "자동대상역할",
        "대상연결상태",
    }
    if not required.issubset(headers):
        raise ValueError("TARGET_LINK_INPUT_COLUMNS_MISSING")
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, found {len(rows)}")

    output_rows: list[dict[str, str]] = []
    patch_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    errors: list[str] = []
    seen: set[str] = set()
    for row in rows:
        grounding = build_target_grounding(row)
        if grounding.claim_id in seen:
            errors.append(f"DUPLICATE_CLAIM_ID:{grounding.claim_id}")
        seen.add(grounding.claim_id)
        status_counts[grounding.status] += 1
        reason_counts[grounding.reason_code] += 1
        patch_json = json.dumps(
            grounding.slot_enrichment_patch,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        output_row = dict(row)
        output_row.update({
            "원문대상연결상태": grounding.status,
            "원문대상연결사유": grounding.reason_code,
            "원문대상표현": grounding.expression,
            "원문대상MentionID": grounding.mention_id,
            "원문대상역할": grounding.role,
            "원문대상시작": "" if grounding.start is None else str(grounding.start),
            "원문대상끝": "" if grounding.end is None else str(grounding.end),
            "파이프라인보강JSON": patch_json,
        })
        output_rows.append(output_row)
        patch_rows.append({
            "claim_id": grounding.claim_id,
            "source_sentence_sha256": hashlib.sha256(
                row["원문"].encode("utf-8")
            ).hexdigest().upper(),
            "target_link_status": grounding.status,
            "target_link_reason_code": grounding.reason_code,
            "slot_enrichment_patch": grounding.slot_enrichment_patch,
        })

    grounded_count = status_counts["SOURCE_GROUNDED"]
    ungrounded_count = len(rows) - grounded_count
    if len(seen) != len(rows):
        errors.append("CLAIM_ID_COUNT_MISMATCH")
    if grounded_count + ungrounded_count != len(rows):
        errors.append("TARGET_LINK_COUNT_MISMATCH")
    if any(not item["target_link_reason_code"] for item in patch_rows):
        errors.append("TARGET_LINK_REASON_MISSING")

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
            handle.write(
                json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    report: dict[str, Any] = {
        "version": 1,
        "verified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "PASS" if not errors else "FAIL",
        "input_count": len(rows),
        "output_count": len(output_rows),
        "unique_claim_id_count": len(seen),
        "grounded_count": grounded_count,
        "ungrounded_count": ungrounded_count,
        "status_counts": dict(status_counts),
        "reason_counts": dict(reason_counts),
        "issues": errors,
        "source": _file(source_csv),
        "outputs": {
            "csv": _file(csv_path),
            "patch_jsonl": _file(patch_path),
        },
    }
    verify_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report["verification_path"] = str(verify_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=381)
    args = parser.parse_args()
    report = build_target_grounding_artifacts(
        source_csv=args.source_csv,
        output_dir=args.output_dir,
        expected_rows=args.expected_rows,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
