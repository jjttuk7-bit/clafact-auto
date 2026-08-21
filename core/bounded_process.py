"""Wall-clock isolation for external workers that may stall inside TLS reads."""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class BoundedProcessResult:
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool


def run_bounded(
    command: Sequence[str],
    *,
    timeout_seconds: float,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
) -> BoundedProcessResult:
    """Run one worker and guarantee termination after the wall-clock budget."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return BoundedProcessResult(process.returncode, stdout, stderr, False)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        return BoundedProcessResult(None, stdout, stderr, True)
