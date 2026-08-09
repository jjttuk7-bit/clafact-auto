"""Logging helpers that avoid recording secrets."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(level: str = "INFO", *, log_path: Path | None = None) -> logging.Logger:
    """Configure console logging and optional size-rotated file logging."""
    logger = logging.getLogger("clafact_auto")
    logger.setLevel(level.upper())
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    if not logger.handlers:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
    if log_path and not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        rotating = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        rotating.setFormatter(formatter)
        logger.addHandler(rotating)
    return logger
