from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app" / "streamlit_app.py"


def test_streamlit_entrypoint_imports_core_when_only_app_directory_is_on_path() -> None:
    """Streamlit Cloud executes the app module from app/, not the repository root."""
    command = f"""
import runpy
import sys
from pathlib import Path

project_root = Path({str(PROJECT_ROOT)!r})
app_path = Path({str(APP_PATH)!r})
sys.path[:] = [str(app_path.parent)] + [
    entry for entry in sys.path if entry not in ("", str(project_root))
]
runpy.run_path(str(app_path), run_name="__streamlit_cloud_test__")
"""

    result = subprocess.run(
        [sys.executable, "-c", command],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr


def test_streamlit_mvp_renders_and_holds_invalid_article_date() -> None:
    app = AppTest.from_file("app/streamlit_app.py")
    app.run()
    assert app.title[0].value == "CLAFACT-AUTO"
    app.text_area[0].input("2024년 전국 고용률은 70%였다.")
    app.text_input[0].input("invalid-date")
    app.button[0].click()
    app.run()
    assert any("HOLD: 기사 기준일은 YYYY-MM-DD 형식이어야 합니다." in element.value for element in app.error)