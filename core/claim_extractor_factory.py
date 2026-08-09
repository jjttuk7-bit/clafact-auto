"""Select one constrained HCX claim extraction boundary from settings."""

from config.settings import Settings
from core.claim_parser import StructuredClaimExtractor
from core.hcx_claim_extractor import HcxClaimExtractor
from core.hcx_function_claim_extractor import HcxFunctionClaimExtractor


def create_claim_extractor(settings: Settings) -> StructuredClaimExtractor:
    """Return only a schema-constrained extractor; never expose verification tools."""
    mode = settings.hcx_extraction_mode.strip().casefold()
    if mode == "structured_output":
        return HcxClaimExtractor(api_key=settings.hcx_api_key)
    if mode == "function_calling":
        return HcxFunctionClaimExtractor(api_key=settings.hcx_api_key)
    raise ValueError(f"HCX_EXTRACTION_MODE_UNSUPPORTED:{mode}")
