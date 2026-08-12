from datetime import date

import pytest

from core.fallback_claim_extractor import FallbackClaimExtractor
from core.openai_function_claim_extractor import (
    OpenAIAuthenticationError,
    OpenAIConfigurationError,
    OpenAIContractError,
    OpenAITransientError,
)
from schemas.claim import ClaimSchema


class FakeExtractor:
    def __init__(self, result: ClaimSchema | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = 0
        self.article_published_at: date | None = None

    def extract(
        self, source_sentence: str, *, article_published_at: date | None = None
    ) -> ClaimSchema:
        self.calls += 1
        self.article_published_at = article_published_at
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def claim(status: str = "AUTO_OK") -> ClaimSchema:
    return ClaimSchema(
        claim_id="claim-1",
        source_sentence="원문",
        parse_status=status,
    )


@pytest.mark.parametrize("status", ["AUTO_OK", "HOLD", "HUMAN_REVIEW"])
def test_valid_primary_result_never_falls_back_for_semantic_status(status: str) -> None:
    expected = claim(status)
    primary = FakeExtractor(result=expected)
    fallback = FakeExtractor(result=claim())
    extractor = FallbackClaimExtractor(primary=primary, fallback=fallback)

    actual = extractor.extract("원문")

    assert actual is expected
    assert primary.calls == 1
    assert fallback.calls == 0
    assert extractor.last_provider == "openai"


@pytest.mark.parametrize("error", [OpenAITransientError("raw"), OpenAIContractError("raw")])
def test_technical_openai_failure_uses_hcx_once(error: Exception) -> None:
    expected = claim()
    primary = FakeExtractor(error=error)
    fallback = FakeExtractor(result=expected)
    extractor = FallbackClaimExtractor(primary=primary, fallback=fallback)

    actual = extractor.extract("원문")

    assert actual is expected
    assert primary.calls == 1
    assert fallback.calls == 1
    assert extractor.last_provider == "hcx"


@pytest.mark.parametrize(
    "error",
    [
        OpenAIConfigurationError("secret details"),
        OpenAIAuthenticationError("secret details"),
        RuntimeError("secret details"),
    ],
)
def test_non_fallback_openai_failure_propagates_without_calling_hcx(error: Exception) -> None:
    primary = FakeExtractor(error=error)
    fallback = FakeExtractor(result=claim())
    extractor = FallbackClaimExtractor(primary=primary, fallback=fallback)

    with pytest.raises(type(error)) as caught:
        extractor.extract("원문")

    assert caught.value is error
    assert primary.calls == 1
    assert fallback.calls == 0
    assert extractor.last_provider == "unavailable"


def test_fallback_failure_propagates_and_provider_remains_unavailable() -> None:
    fallback_error = LookupError("hcx failed")
    primary = FakeExtractor(error=OpenAITransientError("raw openai failure"))
    fallback = FakeExtractor(error=fallback_error)
    extractor = FallbackClaimExtractor(primary=primary, fallback=fallback)

    assert extractor.last_provider == "unavailable"
    with pytest.raises(LookupError) as caught:
        extractor.extract("원문")

    assert caught.value is fallback_error
    assert primary.calls == 1
    assert fallback.calls == 1
    assert extractor.last_provider == "unavailable"


def test_article_date_context_is_forwarded_to_primary_extractor() -> None:
    primary = FakeExtractor(result=claim())
    extractor = FallbackClaimExtractor(primary=primary, fallback=FakeExtractor(result=claim()))

    extractor.extract("원문", article_published_at=date(2025, 4, 5))

    assert primary.article_published_at == date(2025, 4, 5)
