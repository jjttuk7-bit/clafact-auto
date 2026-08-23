from pathlib import Path

from core.multi_claim_group_harness import load_gold_cases
from core.targeted_claim_splitter import discover_numeric_mentions


def test_gold_roles_are_grounded_in_the_exact_discovered_mentions() -> None:
    cases = load_gold_cases(Path("tests/goldset/multi_claim_employment_20.csv"))

    for case in cases:
        mentions = discover_numeric_mentions(case.source_sentence)
        assert tuple(mention.expression for mention in mentions) == case.discovered_expressions
        assert set(case.expected_roles) == {mention.mention_id for mention in mentions}
