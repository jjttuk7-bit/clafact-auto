from __future__ import annotations

import ast
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


def test_example_environment_documents_provider_defaults_without_credentials() -> None:
    lines = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()

    assert lines == [
        "KOSIS_API_KEY=",
        "HCX_API_KEY=",
        "OPENAI_API_KEY=",
        "CLAFACT_CLAIM_PROVIDER=hcx",
        "CLAFACT_OPENAI_MODEL=gpt-5.6-luna",
        "CLAFACT_HCX_EXTRACTION_MODE=structured_output",
        "CLAFACT_LOG_LEVEL=INFO",
    ]


def test_streamlit_app_uses_layout_keywords_supported_by_declared_minimum() -> None:
    source = (PROJECT_ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)]

    assert not any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "container"
        and any(keyword.arg == "horizontal" for keyword in call.keywords)
        for call in calls
    )
    assert not any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "metric"
        and any(keyword.arg == "border" for keyword in call.keywords)
        for call in calls
    )
    assert not any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "dataframe"
        and any(
            keyword.arg == "width"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
            for keyword in call.keywords
        )
        for call in calls
    )
