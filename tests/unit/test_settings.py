from config.settings import Settings, load_environment_file


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


def test_settings_reads_hcx_extraction_mode_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("CLAFACT_HCX_EXTRACTION_MODE", "function_calling")

    assert Settings().hcx_extraction_mode == "function_calling"


def test_load_environment_file_reads_missing_values_without_overwriting_os_environment(tmp_path, monkeypatch) -> None:
    environment_file = tmp_path / ".env"
    environment_file.write_text("KOSIS_API_KEY=file-key\nHCX_API_KEY=file-hcx\n", encoding="utf-8")
    monkeypatch.setenv("KOSIS_API_KEY", "os-key")
    target: dict[str, str] = {"KOSIS_API_KEY": "os-key"}

    load_environment_file(environment_file, target)

    assert target == {"KOSIS_API_KEY": "os-key", "HCX_API_KEY": "file-hcx"}