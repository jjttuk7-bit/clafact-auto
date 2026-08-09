from __future__ import annotations

import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_disables_poetry_package_install_for_streamlit_cloud() -> None:
    """Streamlit Cloud must install dependencies without packaging this app."""
    configuration = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert configuration["tool"]["poetry"]["package-mode"] is False
