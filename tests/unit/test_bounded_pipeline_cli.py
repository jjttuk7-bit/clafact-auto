from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = PROJECT_ROOT / "tools" / "run_clafact_pipeline_bounded.py"


def test_bounded_pipeline_cli_exposes_worker_timeout_and_parallelism() -> None:
    result = subprocess.run(
        [sys.executable, str(CLI_PATH), "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "worker-timeout-seconds" in result.stdout
    assert "max-workers" in result.stdout
