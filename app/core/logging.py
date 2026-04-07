"""Unified logging infrastructure for TelystaLexisEngine.

All modules MUST use ``get_logger(__name__)`` instead of ``print``.

Initialization contract:
  1. First ``get_logger()`` call (from any module import) triggers a minimal
     "safe default" configuration (INFO, no verbose, stdout).
  2. ``bootstrap_app()`` calls ``configure_root(level, verbose, force=True)``
     to override with the actual user-configured settings.
  3. ``force=True`` replaces existing handlers so the second call wins.
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False

DEFAULT_FORMAT = "[%(levelname).1s][%(name)s] %(message)s"
VERBOSE_FORMAT = "%(asctime)s [%(levelname).1s][%(name)s] %(message)s"


def configure_root(
    level: str = "INFO",
    *,
    verbose: bool = False,
    force: bool = False,
) -> None:
    """Configure the root logger.

    Safe to call multiple times. When ``force=True`` the existing
    configuration is replaced (used by bootstrap to apply user settings).
    Without ``force``, a second call is a no-op (module-import guard).
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    _CONFIGURED = True
    fmt = VERBOSE_FORMAT if verbose else DEFAULT_FORMAT
    formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    int_level = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(int_level)

    # Remove stale handlers to avoid duplicate output on forced reconfigure.
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # LLM subsystem always gets DEBUG regardless of root level,
    # so low-level backend calls are visible when investigating issues.
    logging.getLogger("app.llm").setLevel(logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger. Triggers minimal safe default on first call."""
    if not _CONFIGURED:
        configure_root()
    return logging.getLogger(name)
