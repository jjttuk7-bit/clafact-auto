from __future__ import annotations

import sys
import time

from core.bounded_process import run_bounded


def test_run_bounded_terminates_a_stalled_external_worker() -> None:
    started = time.monotonic()

    result = run_bounded(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        timeout_seconds=0.2,
    )

    assert result.timed_out is True
    assert result.return_code is None
    assert time.monotonic() - started < 3
