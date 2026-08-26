"""Audit indicator/unit compatibility for 381 direct-value Claims."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from core.indicator_unit_compatibility import assess_indicator_unit


CSV_NAME = "CLAFACT_8번_직접값_381건_지표단위호환.csv"
PATCH_JSONL_NAME = "CLAFACT_8번_직접값_381건_지표단위호환_파이프라인보강.jsonl"
VERIFY_NAME = "CLAFACT_8번_직접값_381건_지표단위호환_검증.json"
ADDED = [
    "지표단위판정",
    "지표단위판정사유",
    "지표종류",
    "단위종류",
    "허용단위종류",
    "제안지표",
    "지표단위파이프라인보강JSON",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _file(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build_indicator_unit_artifacts(
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
        "지표",
        "단위",
        "원문대상역할",
        "원문대상연결상태",
        "원문대상연결사유",
        "파이프라인보강JSON",
    }
    if not required.issubset(headers):
        raise ValueError("INDICATOR_UNIT_INPUT_COLUMNS_MISSING")
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, found {len(rows)}")

    output_rows: list[dict[str, str]] = []
    patch_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    indicator_family_counts: Counter[str] = Counter()
    unit_family_counts: Counter[str] = Counter()
    seen: set[str] = set()
    issues: list[str] = []
    evaluated_count = 0
    for row in rows:
        claim_id = str(row["Claim번호"]).strip()
        if claim_id in seen:
            issues.append(f"DUPLICATE_CLAIM_ID:{claim_id}")
        seen.add(claim_id)
        try:
            combined_patch = json.loads(row["파이프라인보강JSON"])
        except json.JSONDecodeError as error:
            raise ValueError(f"INDICATOR_UNIT_TARGET_PATCH_INVALID:{claim_id}") from error
        if not isinstance(combined_patch, dict):
            raise ValueError(f"INDICATOR_UNIT_TARGET_PATCH_INVALID:{claim_id}")

        if row["원문대상연결상태"] == "SOURCE_GROUNDED":
            decision = assess_indicator_unit(
                row["지표"], row["단위"], row["원문대상역할"]
            )
            evaluated_count += 1
            status = decision.status
            reason = decision.reason_code
            indicator_family = decision.indicator_family
            unit_family = decision.unit_family
            expected = " | ".join(decision.expected_unit_families)
            suggested = decision.suggested_indicator
            combined_patch.update({
                "indicator_unit_status": status,
                "indicator_unit_reason_code": reason,
                "indicator_measure_family": indicator_family,
                "unit_measure_family": unit_family,
                "indicator_unit_version": "1.0",
                "suggested_indicator": suggested,
            })
            indicator_family_counts[indicator_family] += 1
            unit_family_counts[unit_family] += 1
        else:
            status = "NOT_EVALUATED_TARGET_UNGROUNDED"
            reason = row["원문대상연결사유"]
            indicator_family = ""
            unit_family = ""
            expected = ""
            suggested = ""
            combined_patch.update({
                "indicator_unit_status": status,
                "indicator_unit_reason_code": reason,
                "indicator_unit_version": "1.0",
            })
        status_counts[status] += 1
        reason_counts[reason] += 1
        patch_json = json.dumps(
            combined_patch, ensure_ascii=False, separators=(",", ":")
        )
        output_row = dict(row)
        output_row.update({
            "지표단위판정": status,
            "지표단위판정사유": reason,
            "지표종류": indicator_family,
            "단위종류": unit_family,
            "허용단위종류": expected,
            "제안지표": suggested,
            "지표단위파이프라인보강JSON": patch_json,
        })
        output_rows.append(output_row)
        patch_rows.append({
            "claim_id": claim_id,
            "source_sentence_sha256": hashlib.sha256(
                row["원문"].encode("utf-8")
            ).hexdigest().upper(),
            "indicator_unit_status": status,
            "indicator_unit_reason_code": reason,
            "slot_enrichment_patch": combined_patch,
        })

    unevaluated_count = len(rows) - evaluated_count
    if len(seen) != len(rows):
        issues.append("CLAIM_ID_COUNT_MISMATCH")
    if evaluated_count + unevaluated_count != len(rows):
        issues.append("INDICATOR_UNIT_COUNT_MISMATCH")
    if any(not item["indicator_unit_reason_code"] for item in patch_rows):
        issues.append("INDICATOR_UNIT_REASON_MISSING")

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
        "status": "PASS" if not issues else "FAIL",
        "input_count": len(rows),
        "output_count": len(output_rows),
        "unique_claim_id_count": len(seen),
        "evaluated_count": evaluated_count,
        "unevaluated_count": unevaluated_count,
        "status_counts": dict(status_counts),
        "reason_counts": dict(reason_counts),
        "indicator_family_counts": dict(indicator_family_counts),
        "unit_family_counts": dict(unit_family_counts),
        "issues": issues,
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
    report = build_indicator_unit_artifacts(
        source_csv=args.source_csv,
        output_dir=args.output_dir,
        expected_rows=args.expected_rows,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
