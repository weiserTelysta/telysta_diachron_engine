"""Unified logging infrastructure for TelystaLexisEngine.

All modules MUST use ``get_logger(__name__)`` instead of ``print``.
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False

DEFAULT_FORMAT = "[%(levelname).1s][%(name)s] %(message)s"
VERBOSE_FORMAT = "%(asctime)s [%(levelname).1s][%(name)s] %(message)s"


def configure_root(level: str = "INFO", *, verbose: bool = False) -> None:
    """One-shot root logger configuration. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    fmt = VERBOSE_FORMAT if verbose else DEFAULT_FORMAT
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)

    logging.getLogger("app.llm").setLevel(logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger. Ensures root is configured."""
    if not _CONFIGURED:
        configure_root()
    return logging.getLogger(name)
