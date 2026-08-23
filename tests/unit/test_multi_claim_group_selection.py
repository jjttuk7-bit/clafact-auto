from core.multi_claim_group_harness import GoldClaimCase
from tools.run_multi_claim_group import _select_cases


def _case(claim_id: str) -> GoldClaimCase:
    return GoldClaimCase(
        article_id=claim_id,
        sentence_id="1",
        parent_claim_id=claim_id,
        source_sentence="원문",
        discovered_expressions=(),
        expected_roles={},
        expected_child_count=0,
        expected_route="HUMAN_REVIEW",
    )


def test_select_cases_runs_only_requested_claim_ids_in_gold_order() -> None:
    cases = [_case("c1"), _case("c2"), _case("c3")]

    selected = _select_cases(cases, ["c3", "c1"], limit=20)

    assert [case.parent_claim_id for case in selected] == ["c1", "c3"]
