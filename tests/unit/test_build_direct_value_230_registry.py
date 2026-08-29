import csv
import json
from pathlib import Path

from tools.build_direct_value_230_registry import build_registry


def test_build_registry_preserves_every_type8_row_without_filtering(tmp_path: Path) -> None:
    source = tmp_path / "ledger.csv"
    output = tmp_path / "registry.jsonl"
    manifest = tmp_path / "manifest.json"
    rows = [
        {
            "자식Claim번호": "C1",
            "원본부모Claim번호": "A1_1",
            "원문": "2024년 취업자는 10명이었다.",
            "기사작성일": "2025-01-01",
            "대상수치표현": "10명",
            "지표": "취업자",
            "기사값": "10",
            "단위": "명",
            "기준시점": "2024",
            "주기": "년",
            "계산방식": "DIRECT_VALUE",
            "파싱상태": "AUTO_OK",
        },
        {
            "자식Claim번호": "C2",
            "원본부모Claim번호": "A2_1",
            "원문": "지난달 실업률은 3%였다.",
            "기사작성일": "2025-02-01",
            "대상수치표현": "3%",
            "지표": "실업률",
            "기사값": "3",
            "단위": "%",
            "기준시점": "",
            "주기": "월",
            "계산방식": "DIRECT_VALUE",
            "파싱상태": "HOLD",
            "최종사유코드": "MISSING_TIME",
        },
    ]
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    result = build_registry(source, output, manifest, expected_count=2)

    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert result["record_count"] == 2
    assert [row["claim"]["claim_id"] for row in records] == ["C1", "C2"]
    assert records[1]["claim"]["parse_status"] == "HOLD"
    assert records[0]["source_ref"] == "direct_value_type8_230_final_run"
    assert json.loads(manifest.read_text(encoding="utf-8"))["input_sha256"]
