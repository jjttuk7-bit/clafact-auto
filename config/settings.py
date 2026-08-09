"""Environment-backed application settings with auditable version defaults."""

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuration that never persists credentials to logs or source files."""

    kosis_api_key: str | None = None
    hcx_api_key: str | None = None
    claim_provider: str = "hcx"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-luna"
    log_level: str = "INFO"
    hcx_extraction_mode: str = "structured_output"
    dataset_version: str = "unversioned"
    preprocess_version: str = "1.0"
    claim_schema_version: str = "1.0"
    semantic_standard_version: str = "1.0"
    kosis_catalog_version: str = "1.0"
    matching_version: str = "1.0"
    calculation_version: str = "1.0"

    def __post_init__(self) -> None:
        load_environment_file(_ENV_PATH, environ)
        if self.kosis_api_key is None:
            object.__setattr__(self, "kosis_api_key", getenv("KOSIS_API_KEY"))
        if self.claim_provider == "hcx":
            object.__setattr__(
                self,
                "claim_provider",
                getenv("CLAFACT_CLAIM_PROVIDER", "hcx"),
            )
        object.__setattr__(
            self,
            "claim_provider",
            self.claim_provider.strip().casefold(),
        )
        if self.openai_api_key is None:
            object.__setattr__(self, "openai_api_key", getenv("OPENAI_API_KEY"))
        if self.openai_model == "gpt-5.6-luna":
            object.__setattr__(
                self,
                "openai_model",
                getenv("CLAFACT_OPENAI_MODEL", "gpt-5.6-luna"),
            )
        if self.hcx_api_key is None:
            object.__setattr__(self, "hcx_api_key", getenv("HCX_API_KEY"))
        if self.log_level == "INFO":
            object.__setattr__(self, "log_level", getenv("CLAFACT_LOG_LEVEL", "INFO"))
        if self.hcx_extraction_mode == "structured_output":
            object.__setattr__(
                self,
                "hcx_extraction_mode",
                getenv("CLAFACT_HCX_EXTRACTION_MODE", "structured_output").strip().casefold(),
            )
