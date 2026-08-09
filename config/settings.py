"""Environment-backed application settings with auditable version defaults."""

from dataclasses import dataclass, field
from os import environ, getenv
from pathlib import Path
from typing import MutableMapping


_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def load_environment_file(path: Path, target: MutableMapping[str, str]) -> None:
    """Load simple KEY=VALUE entries without overwriting process environment values."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key.replace("_", "").isalnum():
            target.setdefault(key, value.strip().strip('"').strip("'"))


def _environment_value(name: str, default: str | None = None) -> str | None:
    """Read one setting after centrally loading missing values from .env."""
    load_environment_file(_ENV_PATH, environ)
    return getenv(name, default)


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuration that never persists credentials to logs or source files."""

    kosis_api_key: str | None = field(
        default_factory=lambda: _environment_value("KOSIS_API_KEY"), repr=False
    )
    hcx_api_key: str | None = field(
        default_factory=lambda: _environment_value("HCX_API_KEY"), repr=False
    )
    log_level: str = field(
        default_factory=lambda: _environment_value("CLAFACT_LOG_LEVEL", "INFO")
    )
    hcx_extraction_mode: str = field(
        default_factory=lambda: _environment_value(
            "CLAFACT_HCX_EXTRACTION_MODE", "structured_output"
        )
    )
    dataset_version: str = "unversioned"
    preprocess_version: str = "1.0"
    claim_schema_version: str = "1.0"
    semantic_standard_version: str = "1.0"
    kosis_catalog_version: str = "1.0"
    matching_version: str = "1.0"
    calculation_version: str = "1.0"
    claim_provider: str = field(
        default_factory=lambda: _environment_value("CLAFACT_CLAIM_PROVIDER", "hcx")
    )
    openai_api_key: str | None = field(
        default_factory=lambda: _environment_value("OPENAI_API_KEY"), repr=False
    )
    openai_model: str = field(
        default_factory=lambda: _environment_value("CLAFACT_OPENAI_MODEL", "gpt-5.6-luna")
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "claim_provider",
            self.claim_provider.strip().casefold(),
        )
        object.__setattr__(
            self,
            "hcx_extraction_mode",
            self.hcx_extraction_mode.strip().casefold(),
        )
