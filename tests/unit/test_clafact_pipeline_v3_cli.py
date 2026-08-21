from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_semantic_overlay_pipeline_and_bounded_clis_are_executable() -> None:
    for name in ("run_clafact_pipeline_v3.py", "run_clafact_pipeline_bounded_v3.py"):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / name), "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
