import csv
import json
from pathlib import Path

from tools.build_direct_value_numeric_role_gate_audit import (
    build_numeric_role_gate_artifacts,
)


def _row(claim_id: str, link: str, sign: str) -> dict[str, str]:
    source = "2024년 취업자 수는 2800만명이다."
    expression = "2800만명"
    start = source.index(expression)
    grounded = link == "SOURCE_GROUNDED"
    patch = {
        "target_link_status": link,
        "target_numeric_expression": expression if grounded else "",
        "target_numeric_role": "대상값" if grounded else "",
        "target_numeric_start": start if grounded else None,
        "target_numeric_end": start + len(expression) if grounded else None,
        "indicator_unit_status": "COMPATIBLE" if grounded else "NOT_EVALUATED_TARGET_UNGROUNDED",
        "sign_direction_status": sign,
    }
    return {
        "Claim번호": claim_id,
        "원문": source,
        "원문대상연결상태": link,
        "원문대상연결사유": link,
        "원문대상표현": expression if grounded else "",
        "원문대상역할": "대상값" if grounded else "",
        "원문대상시작": str(start) if grounded else "",
        "원문대상끝": str(start + len(expression)) if grounded else "",
        "부호방향판정": sign,
        "부호방향파이프라인보강JSON": json.dumps(patch, ensure_ascii=False),
    }


def test_builds_integrated_numeric_role_gate_and_preserves_prior_patch(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sign_direction.csv"
    rows = [
        _row("SAFE", "SOURCE_GROUNDED", "NOT_APPLICABLE_LEVEL_VALUE"),
        _row("CONTEXT", "TARGET_CONTEXT_ROLE_CONFLICT", "NOT_EVALUATED_TARGET_UNGROUNDED"),
        _row("MISSING", "TARGET_NOT_FOUND_IN_SOURCE", "NOT_EVALUATED_TARGET_UNGROUNDED"),
        _row("AMBIGUOUS", "TARGET_AMBIGUOUS_IN_SOURCE", "NOT_EVALUATED_TARGET_UNGROUNDED"),
        _row("LEVEL", "SOURCE_GROUNDED", "TARGET_ROLE_REVIEW_REQUIRED"),
    ]
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    report = build_numeric_role_gate_artifacts(
        source_csv=source,
        output_dir=tmp_path / "out",
        expected_rows=5,
    )

    assert report["status"] == "PASS"
    assert report["safe_count"] == 1
    assert report["blocked_count"] == 4
    assert report["status_counts"] == {
        "SAFE_TARGET_ROLE": 1,
        "PROTECTED_CONTEXT_BLOCKED": 1,
        "TARGET_NOT_FOUND_BLOCKED": 1,
        "AMBIGUOUS_TARGET_BLOCKED": 1,
        "LEVEL_ROLE_CONFLICT_BLOCKED": 1,
    }
    output = Path(report["outputs"]["csv"]["path"])
    output_rows = list(csv.DictReader(output.open(encoding="utf-8-sig")))
    assert output_rows[0]["숫자역할자동처리허용"] == "TRUE"
    combined = json.loads(output_rows[0]["숫자역할파이프라인보강JSON"])
    assert combined["target_link_status"] == "SOURCE_GROUNDED"
    assert combined["indicator_unit_status"] == "COMPATIBLE"
    assert combined["numeric_role_gate_status"] == "SAFE_TARGET_ROLE"
    assert Path(report["outputs"]["patch_jsonl"]["path"]).exists()
