from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


_CONFIGURED = False


def _configure_root_logger() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logs_dir = Path(os.getenv("LOG_DIR", "logs"))
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If directory creation fails, we still keep console logging.
        logs_dir = None  # type: ignore[assignment]

    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    if logs_dir is not None:
        file_handler = RotatingFileHandler(
            str(logs_dir / "scanner.log"),
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_root_logger()
    return logging.getLogger(name)

