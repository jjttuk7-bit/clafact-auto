import csv
from pathlib import Path

from core.multi_claim_group_harness import load_gold_cases
from core.targeted_claim_splitter import discover_numeric_mentions


GOLDSET = Path("tests/goldset/multi_claim_representative_20.csv")
LEDGER = Path(
    "artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장.csv"
)
BATCH_ID = "CONTEXT_MULTI_NUMERIC-001"


def test_representative_goldset_matches_the_frozen_ledger_batch() -> None:
    cases = load_gold_cases(GOLDSET)
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_ids = {
        row["Claim번호"] for row in rows if row["대표실행묶음"] == BATCH_ID
    }

    assert len(cases) == 20
    assert {case.parent_claim_id for case in cases} == expected_ids


def test_representative_goldset_uses_exact_deterministic_mentions() -> None:
    cases = load_gold_cases(GOLDSET)

    for case in cases:
        actual = tuple(
            mention.expression
            for mention in discover_numeric_mentions(case.source_sentence)
        )
        assert actual == case.discovered_expressions, case.parent_claim_id
        if case.expected_child_count == 0:
            assert case.expected_route == "HUMAN_REVIEW"
            assert case.expected_roles == {}
        else:
            assert case.expected_roles
            assert set(case.expected_roles) == {
                f"n{index}" for index in range(1, len(actual) + 1)
            }
