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
import shutil
import sys
from datetime import datetime
from pathlib import Path

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
    handler.setLevel(logging.WARNING)
    root.addHandler(handler)

    # LLM subsystem always gets DEBUG regardless of root level,
    # so low-level backend calls are visible when investigating issues.
    logging.getLogger("app.llm").setLevel(logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger. Triggers minimal safe default on first call."""
    if not _CONFIGURED:
        configure_root()
    return logging.getLogger(name)


def _cleanup_old_runs(log_dir: Path, keep: int) -> None:
    """Delete the oldest run directories beyond *keep* most-recent."""
    if keep <= 0:
        return
    runs = sorted(log_dir.glob("run_*"), key=lambda p: p.stat().st_mtime)
    for old in runs[:-keep]:
        shutil.rmtree(old, ignore_errors=True)


def setup_run_logger(seed: int) -> None:
    """Create a per-run log directory and wire file handlers + EventBus.

    Call order: ``_bootstrap()`` must run first so ``global_settings``
    is fully configured before this function reads ``log_retention_count``.
    """
    from app.core.config import configs
    from app.core.event_bus import get_event_bus
    from app.core.settings import global_settings

    log_dir: Path = configs.LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = log_dir / f"run_{seed}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(VERBOSE_FORMAT)
    fh = logging.FileHandler(run_dir / "session.log", encoding="utf-8")
    fh.setFormatter(formatter)
    logging.getLogger().addHandler(fh)

    get_event_bus().setup(run_dir)
    _cleanup_old_runs(log_dir, global_settings.log_retention_count)

    logging.getLogger(__name__).info(
        "Run log directory: %s (seed=%d)", run_dir, seed
    )
