import pytest

from core.multi_claim_group_harness import GoldClaimCase
from tools.merge_multi_claim_group_results import merge_results


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


def test_improved_result_replaces_only_matching_baseline_parent() -> None:
    cases = [_case("c1"), _case("c2")]
    baseline = {
        "c1": {"claim_id": "c1", "status": "OLD"},
        "c2": {"claim_id": "c2", "status": "OLD"},
    }
    improved = {"c2": {"claim_id": "c2", "status": "NEW"}}

    merged = merge_results(cases, baseline, improved)

    assert [row["status"] for row in merged] == ["OLD", "NEW"]


def test_merge_refuses_missing_parent_result() -> None:
    with pytest.raises(ValueError, match="MISSING_MULTI_CLAIM_RESULT"):
        merge_results([_case("c1")], {}, {})
