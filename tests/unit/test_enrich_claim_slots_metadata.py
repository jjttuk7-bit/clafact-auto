from tools.enrich_claim_slots import add_run_metadata


def test_add_run_metadata_includes_non_reversible_openai_fingerprint() -> None:
    secret = "openai-secret"

    result = add_run_metadata(
        {"processed_records": 1},
        provider="openai",
        openai_api_key=secret,
        requested_limit=10,
        source_registry="registry.jsonl",
    )

    assert result["openai_api_key_fingerprint"] == "설정됨 (SHA-256: 9cbbbfb350d0)"
    assert secret not in str(result)


def test_add_run_metadata_omits_openai_fingerprint_for_other_provider() -> None:
    result = add_run_metadata(
        {"processed_records": 1},
        provider="hcx",
        openai_api_key="openai-secret",
        requested_limit=10,
        source_registry="registry.jsonl",
    )

    assert "openai_api_key_fingerprint" not in result