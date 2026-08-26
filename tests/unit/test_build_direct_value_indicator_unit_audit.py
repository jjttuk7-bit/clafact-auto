import csv
import json
from pathlib import Path

from tools.build_direct_value_indicator_unit_audit import build_indicator_unit_artifacts


def _row(claim_id: str, grounded: bool) -> dict[str, str]:
    target_patch = (
        {
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": "23만명",
            "target_numeric_start": 13,
            "target_numeric_end": 17,
        }
        if grounded
        else {
            "target_link_status": "TARGET_NOT_FOUND_IN_SOURCE",
            "target_link_reason_code": "TARGET_NOT_FOUND_IN_SOURCE",
        }
    )
    return {
        "Claim번호": claim_id,
        "원문": "2020년 출생아 수는 23만명이다.",
        "지표": "출생아 수",
        "단위": "명",
        "원문대상역할": "대상값" if grounded else "",
        "원문대상연결상태": "SOURCE_GROUNDED" if grounded else "TARGET_NOT_FOUND_IN_SOURCE",
        "원문대상연결사유": "SOURCE_TARGET_EXACT_MATCH" if grounded else "TARGET_NOT_FOUND_IN_SOURCE",
        "파이프라인보강JSON": json.dumps(target_patch, ensure_ascii=False),
    }


def test_builds_compatibility_csv_and_combined_pipeline_patch(tmp_path: Path) -> None:
    source = tmp_path / "grounded.csv"
    rows = [_row("C1", True), _row("C2", False)]
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    report = build_indicator_unit_artifacts(
        source_csv=source,
        output_dir=tmp_path / "out",
        expected_rows=2,
    )

    assert report["status"] == "PASS"
    assert report["evaluated_count"] == 1
    assert report["unevaluated_count"] == 1
    assert report["status_counts"] == {
        "COMPATIBLE": 1,
        "NOT_EVALUATED_TARGET_UNGROUNDED": 1,
    }
    assert Path(report["outputs"]["csv"]["path"]).exists()
    assert Path(report["outputs"]["patch_jsonl"]["path"]).exists()
