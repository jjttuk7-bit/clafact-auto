from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = PROJECT_ROOT / "tools" / "run_clafact_pipeline.py"


def test_canonical_pipeline_cli_is_directly_executable() -> None:
    result = subprocess.run(
        [sys.executable, str(CLI_PATH), "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "registry_path" in result.stdout
    assert "context-jsonl" in result.stdout
