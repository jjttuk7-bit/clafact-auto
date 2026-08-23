from __future__ import annotations

import csv
from pathlib import Path

from core.multi_claim_group_harness import GoldClaimCase, write_multi_claim_evaluation_csv


def _case() -> GoldClaimCase:
    return GoldClaimCase(
        article_id="A1",
        sentence_id="1",
        parent_claim_id="A1_1",
        source_sentence="고용률은 60%로 전년 58%보다 높았다.",
        discovered_expressions=("60%", "58%"),
        expected_roles={
            "n1": {"role": "MAIN_VALUE", "group_id": "g1"},
            "n2": {"role": "REFERENCE_VALUE", "group_id": "g1"},
        },
        expected_child_count=1,
        expected_route="OFFICIAL_SEARCH",
    )


def _result(second_role: str) -> dict[str, object]:
    return {
        "claim_id": "A1_1",
        "status": "PASS",
        "children": [
            {
                "claim_id": "child-1",
                "admission_route": "KOSIS_PIPELINE_ELIGIBLE",
                "recovery_audit": {
                    "numeric_role_assignments": [
                        {"mention_id": "n1", "expression": "60%", "role": "MAIN_VALUE"},
                        {"mention_id": "n2", "expression": "58%", "role": second_role},
                    ]
                },
            }
        ],
    }


def test_csv_requires_role_and_group_match_not_only_child_count(tmp_path: Path) -> None:
    output = tmp_path / "result.csv"

    write_multi_claim_evaluation_csv(
        [_case()], [_result("MAIN_VALUE")], output, code_version="v", data_version="d"
    )

    row = next(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))
    assert row["개수판정"] == "일치"
    assert row["역할묶음판정"] == "불일치"
    assert row["분리판정"] == "불일치"


def test_csv_accepts_matching_roles_and_same_group_partition(tmp_path: Path) -> None:
    output = tmp_path / "result.csv"

    write_multi_claim_evaluation_csv(
        [_case()], [_result("REFERENCE_VALUE")], output, code_version="v", data_version="d"
    )

    row = next(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))
    assert row["역할묶음판정"] == "일치"
    assert row["분리판정"] == "일치"
