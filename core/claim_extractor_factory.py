"""Select one constrained HCX claim extraction boundary from settings."""

from config.settings import Settings
from core.claim_parser import StructuredClaimExtractor
from core.fallback_claim_extractor import FallbackClaimExtractor
from core.provider_grouping_extractors import (
    HcxFunctionGroupingClaimExtractor,
    HcxGroupingClaimExtractor,
    OpenAIGroupingClaimExtractor,
)


def create_claim_extractor(settings: Settings) -> StructuredClaimExtractor:
    """Return only a schema-constrained extractor; never expose verification tools."""
    provider = settings.claim_provider.strip().casefold()
    if provider == "openai":
        primary = _openai_extractor(settings)
        if settings.hcx_api_key:
            return FallbackClaimExtractor(
                primary=primary,
                fallback=_hcx_extractor(settings, function_calling=False),
            )
        return primary
    if provider != "hcx":
        raise ValueError(f"CLAIM_PROVIDER_UNSUPPORTED:{provider}")
    if not settings.hcx_api_key and settings.openai_api_key:
        return _openai_extractor(settings)

    mode = settings.hcx_extraction_mode.strip().casefold()
    if mode == "structured_output":
        return _hcx_extractor(settings, function_calling=False)
    if mode == "function_calling":
        return _hcx_extractor(settings, function_calling=True)
    raise ValueError(f"HCX_EXTRACTION_MODE_UNSUPPORTED:{mode}")


def _openai_extractor(settings: Settings) -> OpenAIGroupingClaimExtractor:
    return OpenAIGroupingClaimExtractor(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


def _hcx_extractor(
    settings: Settings,
    *,
    function_calling: bool,
) -> StructuredClaimExtractor:
    if function_calling:
        return HcxFunctionGroupingClaimExtractor(api_key=settings.hcx_api_key)
    return HcxGroupingClaimExtractor(api_key=settings.hcx_api_key)
