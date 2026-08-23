from core.claim_group_output_contract import ClaimGroupingOutputPayload


def test_ready_provider_explanation_is_not_treated_as_review_reason() -> None:
    payload = ClaimGroupingOutputPayload.model_validate(
        {
            "status": "READY",
            "reason": "The three numbers belong to one comparison claim.",
            "assignments": [
                {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": "g1"},
            ],
            "groups": [
                {"group_id": "g1", "main_mention_id": "n1", "indicator_hint": "고용률"}
            ],
        }
    )

    plan = payload.to_plan()

    assert plan.status == "READY"
    assert plan.reason is None
