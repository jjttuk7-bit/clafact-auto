import csv
import json
from pathlib import Path

from tools.build_direct_value_target_grounding import build_target_grounding_artifacts


def _row(claim_id: str, status: str) -> dict[str, str]:
    source = "2020년 출생아 수는 23만명이다."
    mentions = [
        {"mention_id": "n1", "expression": "2020년", "start": 0, "end": 5, "context": source},
        {"mention_id": "n2", "expression": "23만명", "start": 13, "end": 17, "context": source},
    ]
    roles = [
        {"mention_id": "n1", "expression": "2020년", "role": "기간", "reason_code": "PERIOD_CONTEXT", "auto_target_eligible": False},
        {"mention_id": "n2", "expression": "23만명", "role": "대상값", "reason_code": "SOURCE_GROUNDED_MAIN", "auto_target_eligible": status == "TARGET_SELECTED"},
    ]
    return {
        "Claim번호": claim_id,
        "원문": source,
        "원문수치목록JSON": json.dumps(mentions, ensure_ascii=False),
        "숫자역할목록JSON": json.dumps(roles, ensure_ascii=False),
        "자동대상표현": "23만명" if status == "TARGET_SELECTED" else "",
        "자동대상역할": "대상값" if status == "TARGET_SELECTED" else "",
        "대상연결상태": status,
    }


def test_builds_csv_patch_jsonl_and_verified_counts(tmp_path: Path) -> None:
    source = tmp_path / "roles.csv"
    rows = [_row("C1", "TARGET_SELECTED"), _row("C2", "NO_TARGET_MATCH")]
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    report = build_target_grounding_artifacts(
        source_csv=source,
        output_dir=tmp_path / "out",
        expected_rows=2,
    )

    assert report["status"] == "PASS"
    assert report["grounded_count"] == 1
    assert report["reason_counts"] == {
        "SOURCE_TARGET_EXACT_MATCH": 1,
        "TARGET_NOT_FOUND_IN_SOURCE": 1,
    }
    assert Path(report["outputs"]["csv"]["path"]).exists()
    assert Path(report["outputs"]["patch_jsonl"]["path"]).exists()
