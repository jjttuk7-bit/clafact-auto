from core.claim_group_validator import validate_grouping_plan
from schemas.claim_group import ClaimGroupingPlan, NumericMention


def test_change_only_claim_can_use_change_value_as_group_anchor() -> None:
    plan = ClaimGroupingPlan.model_validate(
        {
            "status": "READY",
            "assignments": [
                {"mention_id": "n1", "role": "CHANGE_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "CHANGE_VALUE", "group_id": "g2"},
            ],
            "groups": [
                {"group_id": "g1", "main_mention_id": "n1"},
                {"group_id": "g2", "main_mention_id": "n2"},
            ],
        }
    )
    mentions = [
        NumericMention(mention_id="n1", expression="15만명", start=0, end=4),
        NumericMention(mention_id="n2", expression="12만4000명", start=6, end=14),
    ]

    result = validate_grouping_plan(mentions, plan)

    assert result.valid is True
    assert [group.main_expression for group in result.groups] == ["15만명", "12만4000명"]
