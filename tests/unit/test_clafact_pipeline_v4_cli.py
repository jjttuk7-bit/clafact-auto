from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_target_aware_pipeline_clis_are_executable() -> None:
    for name in ("run_clafact_pipeline_v4.py", "run_clafact_pipeline_bounded_v4.py"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / name), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
