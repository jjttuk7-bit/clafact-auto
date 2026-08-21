import pytest

from config.settings import Settings
from tools.reparse_gold_claims import validate_openai_reparse_settings, validate_reparse_summary


def test_cli_requires_openai_provider_and_key() -> None:
    with pytest.raises(RuntimeError, match="OPENAI_PROVIDER_REQUIRED"):
        validate_openai_reparse_settings(Settings(claim_provider="hcx", openai_api_key="secret"))
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY_NOT_CONFIGURED"):
        validate_openai_reparse_settings(Settings(claim_provider="openai", openai_api_key=None))


def test_cli_rejects_any_provider_error_before_publishing_registry() -> None:
    with pytest.raises(RuntimeError, match="CLAIM_REPARSE_BATCH_FAILED"):
        validate_reparse_summary({
            "selected_records": 693,
            "reparse_errors": 1,
        })


def test_cli_accepts_completed_error_free_reparse() -> None:
    validate_reparse_summary({
        "selected_records": 693,
        "reparse_errors": 0,
    })
