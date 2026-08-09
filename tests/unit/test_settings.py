from config.settings import Settings


def test_settings_exposes_required_version_defaults() -> None:
    settings = Settings()

    assert settings.dataset_version == "unversioned"
    assert settings.claim_schema_version == "1.0"
    assert settings.semantic_standard_version == "1.0"
    assert settings.kosis_catalog_version == "1.0"
    assert settings.matching_version == "1.0"
    assert settings.calculation_version == "1.0"


def test_settings_reads_kosis_api_key_only_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("KOSIS_API_KEY", "test-key")

    assert Settings().kosis_api_key == "test-key"


def test_settings_reads_hcx_api_key_only_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("HCX_API_KEY", "test-hcx-key")

    assert Settings().hcx_api_key == "test-hcx-key"
