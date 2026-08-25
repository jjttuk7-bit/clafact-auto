import csv
import json
from pathlib import Path

from core.source_numeric_inventory import inventory_numeric_mentions
from dataclasses import asdict
from tools.build_direct_value_numeric_roles import build_numeric_roles


def test_build_numeric_roles_assigns_every_mention_and_exclusion_reason(tmp_path: Path) -> None:
    source = tmp_path / "inventory.csv"
    sentence = "20대 인구는 2020년 703만명이다."
    mentions = [asdict(item) for item in inventory_numeric_mentions(sentence)]
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Claim번호", "원문", "기사값", "단위", "지표", "원문수치목록JSON"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "Claim번호": "A_1",
                "원문": sentence,
                "기사값": "7030000",
                "단위": "명",
                "지표": "인구",
                "원문수치목록JSON": json.dumps(mentions, ensure_ascii=False),
            }
        )

    result = build_numeric_roles(source_csv=source, output_dir=tmp_path / "out", expected_rows=1)

    assert result["status"] == "PASS"
    assert result["assignment_count"] == 3
    assert result["missing_role_count"] == 0
    assert result["missing_exclusion_reason_count"] == 0
    assert result["protected_role_auto_target_conflict_count"] == 0
