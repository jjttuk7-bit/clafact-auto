from urllib.error import HTTPError

import pytest

from core.fallback_claim_extractor import FallbackClaimExtractor
from core.openai_function_claim_extractor import OpenAIContractError
from schemas.claim_group import NumericMention


class _FailingGrouper:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def group_claims(self, source_sentence: str, mentions: list[NumericMention]) -> object:
        self.calls += 1
        raise self.error


def test_grouping_disables_fallback_after_authentication_failure() -> None:
    primary_error = OpenAIContractError("provider contract failure")
    primary = _FailingGrouper(primary_error)
    fallback = _FailingGrouper(
        HTTPError("https://example.invalid", 401, "Invalid Key", None, None)
    )
    extractor = FallbackClaimExtractor(primary=primary, fallback=fallback)  # type: ignore[arg-type]

    with pytest.raises(OpenAIContractError) as first:
        extractor.group_claims("고용 원문", [])
    with pytest.raises(OpenAIContractError) as second:
        extractor.group_claims("고용 원문", [])

    assert first.value is primary_error
    assert second.value is primary_error
    assert primary.calls == 2
    assert fallback.calls == 1
    assert extractor.last_provider == "unavailable"
