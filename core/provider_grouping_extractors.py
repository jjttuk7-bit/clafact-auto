"""Provider extractors extended with strict numeric role grouping."""

from __future__ import annotations

from core.hcx_claim_extractor import HcxClaimExtractor
from core.hcx_function_claim_extractor import HcxFunctionClaimExtractor
from core.openai_function_claim_extractor import OpenAIFunctionClaimExtractor
from core.provider_claim_groupers import HcxClaimGrouper, OpenAIClaimGrouper, Transport
from schemas.claim_group import ClaimGroupingPlan, NumericMention


class OpenAIGroupingClaimExtractor(OpenAIFunctionClaimExtractor):
    def __init__(self, *, api_key: str | None, model: str, transport: Transport | None = None) -> None:
        super().__init__(api_key=api_key, model=model, transport=transport)
        self._grouper = OpenAIClaimGrouper(
            api_key=api_key,
            model=model,
            transport=transport,
        )

    def group_claims(
        self,
        source_sentence: str,
        mentions: list[NumericMention],
    ) -> ClaimGroupingPlan:
        return self._grouper.group_claims(source_sentence, mentions)


class HcxGroupingClaimExtractor(HcxClaimExtractor):
    def __init__(self, *, api_key: str | None, model: str = "HCX-007") -> None:
        super().__init__(api_key=api_key, model=model)
        self._grouper = HcxClaimGrouper(api_key=api_key, model=model)

    def group_claims(
        self,
        source_sentence: str,
        mentions: list[NumericMention],
    ) -> ClaimGroupingPlan:
        return self._grouper.group_claims(source_sentence, mentions)


class HcxFunctionGroupingClaimExtractor(HcxFunctionClaimExtractor):
    def __init__(self, *, api_key: str | None, model: str = "HCX-007") -> None:
        super().__init__(api_key=api_key, model=model)
        self._grouper = HcxClaimGrouper(api_key=api_key, model=model)

    def group_claims(
        self,
        source_sentence: str,
        mentions: list[NumericMention],
    ) -> ClaimGroupingPlan:
        return self._grouper.group_claims(source_sentence, mentions)
