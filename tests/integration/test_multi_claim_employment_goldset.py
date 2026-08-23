from pathlib import Path

from core.multi_claim_group_harness import load_gold_cases


GOLDSET = Path("tests/goldset/multi_claim_employment_20.csv")


def test_employment_goldset_has_twenty_unique_auditable_cases() -> None:
    cases = load_gold_cases(GOLDSET)

    assert len(cases) == 20
    assert len({case.parent_claim_id for case in cases}) == 20
    assert all(case.source_sentence for case in cases)
    assert all(len(case.discovered_expressions) >= 2 for case in cases)
    assert all(case.expected_child_count >= 1 for case in cases)
    assert all(case.expected_roles for case in cases)
