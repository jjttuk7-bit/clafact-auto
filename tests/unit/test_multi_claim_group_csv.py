from __future__ import annotations

import csv
from pathlib import Path

from core.multi_claim_group_harness import (
    GoldClaimCase,
    write_multi_claim_evaluation_csv,
)


EXPECTED_HEADERS = {
    "기사번호",
    "문장번호",
    "부모Claim번호",
    "원문",
    "발견수치",
    "기대역할표",
    "실제역할표",
    "기대자식수",
    "실제자식수",
    "분리판정",
    "자식Claim번호",
    "12개항목상태",
    "재입장결과",
    "중단사유",
    "코드버전",
    "자료버전",
    "실행시각",
}


def test_evaluation_csv_contains_expected_actual_and_child_audit(tmp_path: Path) -> None:
    case = GoldClaimCase(
        article_id="A1",
        sentence_id="2",
        parent_claim_id="A1_2",
        source_sentence="고용률은 60%로 전년 58%보다 2%포인트 올랐다.",
        discovered_expressions=("60%", "58%", "2%포인트"),
        expected_roles={
            "n1": {"role": "MAIN_VALUE", "group_id": "g1"},
            "n2": {"role": "REFERENCE_VALUE", "group_id": "g1"},
            "n3": {"role": "CHANGE_VALUE", "group_id": "g1"},
        },
        expected_child_count=1,
        expected_route="OFFICIAL_SEARCH",
    )
    result = {
        "claim_id": "A1_2",
        "status": "PASS",
        "reason_code": "KOSIS_PIPELINE_ELIGIBLE",
        "children": [
            {
                "claim_id": "child-1",
                "admission_route": "KOSIS_PIPELINE_ELIGIBLE",
                "twelve_slot_complete": True,
                "slot_audit": {
                    "entries": [{"slot": "indicator", "status": "SOURCE"}],
                    "reason_codes": [],
                },
                "recovery_audit": {
                    "numeric_roles": {
                        "60%": "MAIN_VALUE",
                        "58%": "REFERENCE_VALUE",
                        "2%포인트": "CHANGE_VALUE",
                    }
                },
            }
        ],
    }
    output = tmp_path / "result.csv"

    write_multi_claim_evaluation_csv(
        [case],
        [result],
        output,
        code_version="abc123",
        data_version="data456",
    )

    raw = output.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))
    assert EXPECTED_HEADERS <= set(rows[0])
    assert rows[0]["기대자식수"] == "1"
    assert rows[0]["실제자식수"] == "1"
    assert rows[0]["분리판정"] == "일치"
    assert rows[0]["재입장결과"] == "KOSIS_PIPELINE_ELIGIBLE"


def test_evaluation_csv_records_parent_even_when_no_child_is_created(tmp_path: Path) -> None:
    case = GoldClaimCase(
        article_id="A2",
        sentence_id="3",
        parent_claim_id="A2_3",
        source_sentence="수치 관계가 모호하다.",
        discovered_expressions=(),
        expected_roles={},
        expected_child_count=0,
        expected_route="HUMAN_REVIEW",
    )
    output = tmp_path / "result.csv"

    write_multi_claim_evaluation_csv(
        [case],
        [{"claim_id": "A2_3", "status": "HUMAN_REVIEW", "reason_code": "GROUPING_AMBIGUOUS", "children": []}],
        output,
        code_version="abc123",
        data_version="data456",
    )

    rows = list(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 1
    assert rows[0]["자식Claim번호"] == ""
    assert rows[0]["중단사유"] == "GROUPING_AMBIGUOUS"
