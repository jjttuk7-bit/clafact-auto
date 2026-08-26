import csv
import json
from pathlib import Path

from tools.build_direct_value_sign_direction_audit import (
    build_sign_direction_artifacts,
)


def _row(claim_id: str, grounded: bool) -> dict[str, str]:
    source = "취업자가 3만5000명 늘었다."
    expression = "3만5000명"
    start = source.index(expression)
    patch = (
        {
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": expression,
            "target_numeric_role": "증감값",
            "target_numeric_start": start,
            "target_numeric_end": start + len(expression),
            "indicator_unit_status": "COMPATIBLE",
        }
        if grounded
        else {
            "target_link_status": "TARGET_NOT_FOUND_IN_SOURCE",
            "indicator_unit_status": "NOT_EVALUATED_TARGET_UNGROUNDED",
        }
    )
    return {
        "Claim번호": claim_id,
        "원문": source,
        "지표": "취업자 수",
        "기사값": "35000",
        "단위": "명",
        "조건": "",
        "원문대상표현": expression if grounded else "",
        "원문대상역할": "증감값" if grounded else "",
        "원문대상시작": str(start) if grounded else "",
        "원문대상끝": str(start + len(expression)) if grounded else "",
        "원문대상연결상태": "SOURCE_GROUNDED" if grounded else "TARGET_NOT_FOUND_IN_SOURCE",
        "지표단위파이프라인보강JSON": json.dumps(patch, ensure_ascii=False),
    }


def test_builds_sign_direction_csv_and_combined_patch(tmp_path: Path) -> None:
    source = tmp_path / "indicator_unit.csv"
    rows = [_row("C1", True), _row("C2", False)]
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    report = build_sign_direction_artifacts(
        source_csv=source,
        output_dir=tmp_path / "out",
        expected_rows=2,
    )

    assert report["status"] == "PASS"
    assert report["evaluated_count"] == 1
    assert report["unevaluated_count"] == 1
    assert report["status_counts"] == {
        "SOURCE_DIRECTION_RECOVERED": 1,
        "NOT_EVALUATED_TARGET_UNGROUNDED": 1,
    }
    output = Path(report["outputs"]["csv"]["path"])
    result_rows = list(csv.DictReader(output.open(encoding="utf-8-sig")))
    assert result_rows[0]["원문방향"] == "INCREASE"
    assert result_rows[0]["계산용부호값"] == "35000.0"
    assert Path(report["outputs"]["patch_jsonl"]["path"]).exists()
