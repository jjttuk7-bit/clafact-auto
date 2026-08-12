"""Secret-safe stage diagnostics for unexpected operational failures."""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
import traceback
from typing import TypeVar
from uuid import uuid4


T = TypeVar("T")
logger = logging.getLogger(__name__)


class OperationalStageError(RuntimeError):
    """Expose only the failed pipeline stage and an opaque diagnostic reference."""

    def __init__(self, stage: str, diagnostic_id: str) -> None:
        self.stage = stage
        self.diagnostic_id = diagnostic_id
        self.safe_message = f"{stage} 단계 처리 오류 · 진단 ID {diagnostic_id}"
        super().__init__(self.safe_message)


def run_operational_stage(
    stage: str,
    operation: Callable[[], T],
    *,
    diagnostic_id_factory: Callable[[], str] | None = None,
) -> T:
    """Run one adapter boundary and replace unexpected errors with a safe reference."""
    try:
        return operation()
    except OperationalStageError:
        raise
    except Exception as error:
        diagnostic_id = (diagnostic_id_factory or _diagnostic_id)()
        frames = " > ".join(
            f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
            for frame in traceback.extract_tb(error.__traceback__)
        )
        logger.error(
            "operational_failure stage=%s diagnostic_id=%s exception_type=%s frames=%s",
            stage,
            diagnostic_id,
            type(error).__name__,
            frames,
        )
        raise OperationalStageError(stage, diagnostic_id) from None


def _diagnostic_id() -> str:
    return uuid4().hex[:12]
