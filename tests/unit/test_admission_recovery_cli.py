from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import tools.run_admission_recovery_batch as cli


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = PROJECT_ROOT / "tools" / "run_admission_recovery_batch.py"


def test_recovery_cli_can_be_invoked_as_a_script() -> None:
    result = subprocess.run(
        [sys.executable, str(CLI_PATH), "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "registry_path" in result.stdout


def test_recovery_cli_has_no_debug_only_startup_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    class StartupReached(RuntimeError):
        pass

    def settings_after_argument_parsing() -> object:
        raise StartupReached

    monkeypatch.setattr(cli, "Settings", settings_after_argument_parsing)
    monkeypatch.setattr(sys, "argv", ["run_admission_recovery_batch", "input.jsonl", "output"])

    with pytest.raises(StartupReached):
        cli.main()
