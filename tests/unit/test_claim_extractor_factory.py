import pytest

from config.settings import Settings
from core.claim_extractor_factory import create_claim_extractor
from core.hcx_claim_extractor import HcxClaimExtractor
from core.hcx_function_claim_extractor import HcxFunctionClaimExtractor


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
