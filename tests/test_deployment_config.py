from __future__ import annotations

import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_cloud_uses_requirements_without_poetry_lock_generation() -> None:
    """Cloud must not select Poetry and mutate its checkout with a generated lock file."""
    configuration = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()

    assert "poetry" not in configuration.get("tool", {})
    assert "streamlit>=1.40" in requirements
    assert "pydantic>=2.0,<3.0" in requirements
