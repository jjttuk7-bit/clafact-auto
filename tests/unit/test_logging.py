from logging.handlers import RotatingFileHandler

from config.logging import configure_logging


def test_configure_logging_uses_rotating_file_handler(tmp_path) -> None:
    logger = configure_logging("INFO", log_path=tmp_path / "engine.log")
    assert any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers)
