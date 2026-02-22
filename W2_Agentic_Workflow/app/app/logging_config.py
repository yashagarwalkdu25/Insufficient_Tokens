"""
Central logging setup for TripSaathi.
Clear, readable logs: [timestamp] LEVEL [module] message
Set LOG_LEVEL=DEBUG in env for verbose output (default INFO).
"""
from __future__ import annotations

import logging
import os
import sys


_configured = False


def setup_logging(
    level: str | None = None,
    format_string: str | None = None,
) -> None:
    """
    Configure logging for the app. Call once at startup (e.g. in main.py).
    Only runs once per process so Streamlit reruns don't duplicate logs or reorder them.
    """
    global _configured
    if _configured:
        return
    _configured = True

    level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    numeric = getattr(logging, level, logging.INFO)

    format_string = (
        format_string
        or "[%(asctime)s] %(levelname)-5s [%(name)s] %(message)s"
    )
    date_fmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(numeric)

    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(numeric)
    handler.setFormatter(logging.Formatter(format_string, datefmt=date_fmt))
    root.addHandler(handler)

    logging.getLogger("app").setLevel(numeric)
    if numeric > logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("langgraph").setLevel(logging.WARNING)
        logging.getLogger("langchain").setLevel(logging.WARNING)

    logging.getLogger("app").info("Logging configured | level=%s", level)


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module name (e.g. __name__)."""
    return logging.getLogger(name)
