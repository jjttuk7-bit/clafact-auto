"""Audit source-grounded sign and direction for 381 direct-value Claims."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from core.source_sign_direction import assess_source_sign_direction


CSV_NAME = "CLAFACT_8번_직접값_381건_부호방향보존.csv"
PATCH_JSONL_NAME = "CLAFACT_8번_직접값_381건_부호방향보존_파이프라인보강.jsonl"
VERIFY_NAME = "CLAFACT_8번_직접값_381건_부호방향보존_검증.json"
ADDED = [
    "부호방향판정",
    "부호방향사유",
    "원문방향",
    "원문극성",
    "저장방향",
    "원래기사값",
    "계산용부호값",
    "부호근거문구",
    "부호근거시작",
    "부호근거끝",
    "부호방향파이프라인보강JSON",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _file(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build_sign_direction_artifacts(
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
        "기사값",
        "조건",
        "원문대상표현",
        "원문대상역할",
        "원문대상시작",
        "원문대상끝",
        "원문대상연결상태",
        "지표단위파이프라인보강JSON",
    }
    if not required.issubset(headers):
        raise ValueError("SIGN_DIRECTION_INPUT_COLUMNS_MISSING")
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, found {len(rows)}")

    output_rows: list[dict[str, str]] = []
    patch_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    direction_counts: Counter[str] = Counter()
    polarity_counts: Counter[str] = Counter()
    seen: set[str] = set()
    issues: list[str] = []
    evaluated_count = 0
    signed_count = 0
    for row in rows:
        claim_id = str(row["Claim번호"]).strip()
        if not claim_id:
            issues.append("EMPTY_CLAIM_ID")
        if claim_id in seen:
            issues.append(f"DUPLICATE_CLAIM_ID:{claim_id}")
        seen.add(claim_id)
        combined_patch = _json_object(
            row["지표단위파이프라인보강JSON"],
            f"SIGN_DIRECTION_PRIOR_PATCH_INVALID:{claim_id}",
        )
        if row["원문대상연결상태"] == "SOURCE_GROUNDED":
            condition = _json_object(row["조건"], f"SIGN_DIRECTION_CONDITION_INVALID:{claim_id}")
            try:
                value = float(row["기사값"])
                start = int(row["원문대상시작"])
                end = int(row["원문대상끝"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"SIGN_DIRECTION_NUMERIC_INPUT_INVALID:{claim_id}") from error
            decision = assess_source_sign_direction(
                source_sentence=row["원문"],
                indicator=row["지표"],
                value=value,
                target_expression=row["원문대상표현"],
                target_role=row["원문대상역할"],
                target_start=start,
                target_end=end,
                stored_condition=condition,
            )
            evaluated_count += 1
            status = decision.status
            reason = decision.reason_code
            direction = decision.source_direction
            polarity = decision.source_polarity
            stored_direction = decision.stored_direction
            original_value = decision.original_value
            signed_value = decision.signed_target_value
            basis_text = decision.basis_text
            basis_start = decision.basis_start
            basis_end = decision.basis_end
            combined_patch.update({
                "sign_direction_status": status,
                "sign_direction_reason_code": reason,
                "source_direction": direction,
                "source_polarity": polarity,
                "original_claim_value": original_value,
                "signed_target_value": signed_value,
                "sign_basis_text": basis_text,
                "sign_basis_start": basis_start,
                "sign_basis_end": basis_end,
                "stored_direction_before_sign_audit": stored_direction,
                "original_condition_before_sign_audit": condition,
                "sign_direction_version": "1.0",
            })
            if signed_value is not None:
                signed_count += 1
                if not (direction or polarity) or not basis_text:
                    issues.append(f"SIGN_EVIDENCE_MISSING:{claim_id}")
            if direction:
                direction_counts[direction] += 1
            if polarity:
                polarity_counts[polarity] += 1
        else:
            status = "NOT_EVALUATED_TARGET_UNGROUNDED"
            reason = str(row.get("원문대상연결사유") or row["원문대상연결상태"])
            direction = ""
            polarity = ""
            stored_direction = ""
            original_value = _optional_float(row.get("기사값"))
            signed_value = None
            basis_text = ""
            basis_start = None
            basis_end = None
            combined_patch.update({
                "sign_direction_status": status,
                "sign_direction_reason_code": reason,
                "sign_direction_version": "1.0",
            })
        status_counts[status] += 1
        reason_counts[reason] += 1
        patch_json = json.dumps(combined_patch, ensure_ascii=False, separators=(",", ":"))
        output_row = dict(row)
        output_row.update({
            "부호방향판정": status,
            "부호방향사유": reason,
            "원문방향": direction,
            "원문극성": polarity,
            "저장방향": stored_direction,
            "원래기사값": "" if original_value is None else str(original_value),
            "계산용부호값": "" if signed_value is None else str(signed_value),
            "부호근거문구": basis_text,
            "부호근거시작": "" if basis_start is None else str(basis_start),
            "부호근거끝": "" if basis_end is None else str(basis_end),
            "부호방향파이프라인보강JSON": patch_json,
        })
        output_rows.append(output_row)
        patch_rows.append({
            "claim_id": claim_id,
            "source_sentence_sha256": hashlib.sha256(row["원문"].encode("utf-8")).hexdigest().upper(),
            "sign_direction_status": status,
            "sign_direction_reason_code": reason,
            "slot_enrichment_patch": combined_patch,
        })

    unevaluated_count = len(rows) - evaluated_count
    if len(seen) != len(rows):
        issues.append("CLAIM_ID_COUNT_MISMATCH")
    if any(not item["sign_direction_reason_code"] for item in patch_rows):
        issues.append("SIGN_DIRECTION_REASON_MISSING")

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
        "evaluated_count": evaluated_count,
        "unevaluated_count": unevaluated_count,
        "signed_count": signed_count,
        "status_counts": dict(status_counts),
        "reason_counts": dict(reason_counts),
        "direction_counts": dict(direction_counts),
        "polarity_counts": dict(polarity_counts),
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


def _json_object(raw: str | None, reason: str) -> dict[str, Any]:
    if not str(raw or "").strip():
        return {}
    try:
        value = json.loads(str(raw))
    except json.JSONDecodeError as error:
        raise ValueError(reason) from error
    if not isinstance(value, dict):
        raise ValueError(reason)
    return value


def _optional_float(raw: str | None) -> float | None:
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=381)
    args = parser.parse_args()
    report = build_sign_direction_artifacts(
        source_csv=args.source_csv,
        output_dir=args.output_dir,
        expected_rows=args.expected_rows,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
