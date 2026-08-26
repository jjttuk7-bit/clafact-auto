import csv
import json
from pathlib import Path

import pytest

from tools.build_direct_value_numeric_inventory import build_inventory


def _write_input(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Claim번호", "원문", "기사값", "단위"])
        writer.writeheader()
        writer.writerows(rows)


def test_build_inventory_writes_one_complete_row_per_claim(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    _write_input(
        source,
        [
            {"Claim번호": "A_1", "원문": "20대 인구는 2020년 703만명이다.", "기사값": "7030000", "단위": "명"},
            {"Claim번호": "A_2", "원문": "성장률은 3~4%였다.", "기사값": "4", "단위": "%"},
        ],
    )

    result = build_inventory(source_csv=source, output_dir=tmp_path / "out", expected_rows=2)

    assert result["status"] == "PASS"
    assert result["input_count"] == 2
    assert result["output_count"] == 2
    assert result["unique_claim_id_count"] == 2
    assert result["uncovered_digit_count"] == 0
    assert result["position_mismatch_count"] == 0
    with Path(result["outputs"]["csv"]["path"]).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mentions = json.loads(rows[0]["원문수치목록JSON"])
    assert [mention["expression"] for mention in mentions] == ["20대", "2020년", "703만명"]
    assert all(mention["role_status"] == "미분류" for mention in mentions)


def test_build_inventory_fails_on_duplicate_claim_id(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    _write_input(
        source,
        [
            {"Claim번호": "A_1", "원문": "10명이다.", "기사값": "10", "단위": "명"},
            {"Claim번호": "A_1", "원문": "20명이다.", "기사값": "20", "단위": "명"},
        ],
    )

    with pytest.raises(ValueError, match="duplicate Claim번호"):
        build_inventory(source_csv=source, output_dir=tmp_path / "out", expected_rows=2)
