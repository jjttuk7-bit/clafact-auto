import logging

import pytest

from core.operational_error import OperationalStageError, run_operational_stage


def test_run_operational_stage_returns_successful_result() -> None:
    assert run_operational_stage("CLAIM_PARSE", lambda: "ok") == "ok"


def test_run_operational_stage_replaces_exception_with_safe_stage_reference(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail() -> None:
        raise TypeError("apiKey=must-not-appear")

    with caplog.at_level(logging.ERROR), pytest.raises(OperationalStageError) as caught:
        run_operational_stage(
            "KOSIS_CATALOG",
            fail,
            diagnostic_id_factory=lambda: "diag12345678",
        )

    error = caught.value
    assert error.stage == "KOSIS_CATALOG"
    assert error.diagnostic_id == "diag12345678"
    assert error.safe_message == "KOSIS_CATALOG 단계 처리 오류 · 진단 ID diag12345678"
    assert "TypeError" in caplog.text
    assert "apiKey=must-not-appear" not in caplog.text
