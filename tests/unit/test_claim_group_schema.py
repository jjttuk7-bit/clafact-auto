import pytest
from pydantic import ValidationError

from schemas.claim_group import ClaimGroupingPlan


def test_group_plan_requires_one_main_value_per_claim_group() -> None:
    with pytest.raises(ValidationError):
        ClaimGroupingPlan.model_validate(
            {
                "status": "READY",
                "assignments": [
                    {
                        "mention_id": "n1",
                        "role": "REFERENCE_VALUE",
                        "group_id": "g1",
                    }
                ],
                "groups": [{"group_id": "g1", "main_mention_id": "n1"}],
            }
        )


def test_human_review_plan_cannot_contain_automatic_groups() -> None:
    with pytest.raises(ValidationError):
        ClaimGroupingPlan.model_validate(
            {
                "status": "HUMAN_REVIEW",
                "reason": "AMBIGUOUS",
                "assignments": [],
                "groups": [{"group_id": "g1", "main_mention_id": "n1"}],
            }
        )
