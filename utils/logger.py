"""Logging setup.

INFO, WARNING and ERROR(+CRITICAL) records are written to their own log
files under `logs/`, in addition to a combined console stream. This
keeps day-to-day activity, non-fatal warnings (retries, rate limits) and
hard failures easy to inspect independently.
"""

from __future__ import annotations

import logging
from pathlib import Path


class _ExactLevelFilter(logging.Filter):
    """Only lets records of exactly one level through a handler."""

    def __init__(self, level: int) -> None:
        super().__init__()
        self._level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == self._level


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    info_handler = logging.FileHandler(log_dir / "info.log", encoding="utf-8")
    info_handler.setFormatter(formatter)
    info_handler.addFilter(_ExactLevelFilter(logging.INFO))
    root.addHandler(info_handler)

    warning_handler = logging.FileHandler(log_dir / "warning.log", encoding="utf-8")
    warning_handler.setFormatter(formatter)
    warning_handler.addFilter(_ExactLevelFilter(logging.WARNING))
    root.addHandler(warning_handler)

    error_handler = logging.FileHandler(log_dir / "error.log", encoding="utf-8")
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    root.addHandler(error_handler)

    # Quiet down noisy third-party loggers.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
