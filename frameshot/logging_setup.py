"""Logging configuration.

Console output stays readable for end users; the rotating file under
``paths.log_dir`` is what we ask for in bug reports.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
LOG_FILENAME = "frameshot.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3

_configured = False


def configure_logging(
    level: str | int = "INFO",
    log_dir: str | Path | None = None,
) -> None:
    """Install console and (optionally) rotating-file handlers.

    Safe to call more than once: subsequent calls only adjust the level.
    """
    global _configured

    root = logging.getLogger()
    numeric_level = logging.getLevelName(level) if isinstance(level, str) else level
    if not isinstance(numeric_level, int):
        raise ValueError(f"invalid log level: {level!r}")

    if _configured:
        root.setLevel(numeric_level)
        return

    formatter = logging.Formatter(LOG_FORMAT)

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_dir is not None:
        directory = Path(log_dir)
        try:
            directory.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                directory / LOG_FILENAME,
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
        except OSError as exc:  # read-only location: console logging still works
            root.warning("file logging disabled (%s)", exc)
        else:
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)

    root.setLevel(numeric_level)
    _configured = True
