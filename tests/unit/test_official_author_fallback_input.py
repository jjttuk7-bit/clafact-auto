import csv
import json
from pathlib import Path

import pytest

from core.official_author_fallback_input import (
    freeze_catalog_failures,
    select_catalog_failures,
)


def _row(claim_id: str, reason_code: str) -> dict[str, object]:
    return {
        "article_id": "A1",
        "sentence_id": "1",
        "claim_id": claim_id,
        "parent_claim_id": claim_id,
        "reason_code": reason_code,
        "terminal_status": "HOLD",
        "claim": {
            "claim_id": claim_id,
            "source_sentence": f"{claim_id} 원문",
            "indicator": "지표",
            "value": 1,
            "unit": "%",
            "time": "2024",
        },
    }


def test_selects_only_catalog_failures_and_requires_exact_expected_count() -> None:
    rows = [_row("c1", "KOSIS_CATALOG_UNAVAILABLE"), _row("c2", "NO_HARD_GUARD_CANDIDATE")]

    selected = select_catalog_failures(rows, expected_count=1)

    assert [row["claim_id"] for row in selected] == ["c1"]
    with pytest.raises(ValueError, match="EXPECTED_5_CATALOG_FAILURES"):
        select_catalog_failures(rows, expected_count=5)


def test_freeze_writes_same_five_ids_to_jsonl_and_before_csv(tmp_path: Path) -> None:
    rows = [_row(f"c{index}", "KOSIS_CATALOG_UNAVAILABLE") for index in range(5)]
    jsonl_path = tmp_path / "input_registry.jsonl"
    csv_path = tmp_path / "before.csv"

    freeze_catalog_failures(rows, jsonl_path=jsonl_path, csv_path=csv_path, expected_count=5)

    frozen = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        before = list(csv.DictReader(source))
    assert [row["claim_id"] for row in frozen] == [f"c{index}" for index in range(5)]
    assert [row["자식Claim번호"] for row in before] == [f"c{index}" for index in range(5)]
    assert all(row["개선전중단사유"] == "KOSIS_CATALOG_UNAVAILABLE" for row in before)
