import pytest

from config.settings import Settings
from core.claim_extractor_factory import create_claim_extractor
from core.fallback_claim_extractor import FallbackClaimExtractor
from core.hcx_claim_extractor import HcxClaimExtractor
from core.hcx_function_claim_extractor import HcxFunctionClaimExtractor
from core.openai_function_claim_extractor import OpenAIFunctionClaimExtractor


def test_factory_uses_structured_output_by_default() -> None:
    extractor = create_claim_extractor(Settings(hcx_api_key="test-key"))

    assert isinstance(extractor, HcxClaimExtractor)


def test_factory_selects_constrained_function_calling() -> None:
    extractor = create_claim_extractor(
        Settings(hcx_api_key="test-key", hcx_extraction_mode="function_calling")
    )

    assert isinstance(extractor, HcxFunctionClaimExtractor)


def test_factory_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="HCX_EXTRACTION_MODE_UNSUPPORTED"):
        create_claim_extractor(Settings(hcx_api_key="test-key", hcx_extraction_mode="agent"))


def test_factory_selects_openai_without_fallback_when_hcx_key_is_absent(monkeypatch) -> None:
    monkeypatch.delenv("HCX_API_KEY", raising=False)
    extractor = create_claim_extractor(
        Settings(
            claim_provider="openai",
            openai_api_key="openai-key",
            openai_model="gpt-test",
            hcx_api_key=None,
        )
    )

    assert isinstance(extractor, OpenAIFunctionClaimExtractor)
    assert extractor.api_key == "openai-key"
    assert extractor.model == "gpt-test"


def test_factory_wraps_openai_with_structured_hcx_fallback() -> None:
    extractor = create_claim_extractor(
        Settings(
            claim_provider="openai",
            openai_api_key="openai-key",
            hcx_api_key="hcx-key",
            hcx_extraction_mode="function_calling",
        )
    )

    assert isinstance(extractor, FallbackClaimExtractor)
    assert isinstance(extractor.primary, OpenAIFunctionClaimExtractor)
    assert isinstance(extractor.fallback, HcxClaimExtractor)
    assert not isinstance(extractor.fallback, HcxFunctionClaimExtractor)


def test_factory_rejects_unknown_provider_with_stable_error() -> None:
    with pytest.raises(ValueError, match=r"^CLAIM_PROVIDER_UNSUPPORTED:local$"):
        create_claim_extractor(Settings(claim_provider=" LOCAL ", hcx_api_key="test-key"))
