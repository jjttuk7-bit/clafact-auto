from core.fallback_claim_extractor import FallbackClaimExtractor
from core.openai_function_claim_extractor import OpenAIContractError
from schemas.claim_group import ClaimGroupingPlan, NumericMention


def _plan() -> ClaimGroupingPlan:
    return ClaimGroupingPlan.model_validate(
        {
            "status": "READY",
            "reason": None,
            "assignments": [
                {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"}
            ],
            "groups": [{"group_id": "g1", "main_mention_id": "n1"}],
        }
    )


class _GroupingExtractor:
    def __init__(self, *, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    def group_claims(self, source_sentence, mentions):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def test_grouping_falls_back_once_only_for_contract_or_transient_failure() -> None:
    primary = _GroupingExtractor(error=OpenAIContractError("bad"))
    fallback = _GroupingExtractor(result=_plan())
    extractor = FallbackClaimExtractor(primary=primary, fallback=fallback)
    mentions = [NumericMention(mention_id="n1", expression="60%", start=0, end=3)]

    actual = extractor.group_claims("60%", mentions)

    assert actual == _plan()
    assert primary.calls == 1
    assert fallback.calls == 1
    assert extractor.last_provider == "hcx"
