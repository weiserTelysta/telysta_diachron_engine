"""Structured per-domain log writer for a single engine run.

Writes pipe-delimited lines to per-domain log files inside the active
run directory.  All modules call ``get_event_bus().emit(...)`` without
knowing the file path.

Line format::

    2026-04-07T14:30:22 | engine | ERA_END          | era=42 alive=285 changes=7

The bus is a process-global singleton.  ``setup()`` is called once per
run (by ``setup_run_logger``); subsequent emits go to the same files
until the next ``setup()`` call or ``close()``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import IO


class EventBus:
    """Singleton structured log writer.

    Domains map to files:  engine → engine.log,  epoch → epoch.log,
    llm → llm.log.  Unknown domains are silently ignored so callers
    never raise on an uninitialized bus.
    """

    _DOMAINS = ("engine", "epoch", "llm")

    def __init__(self) -> None:
        self._writers: dict[str, IO[str]] = {}
        self._run_dir: Path | None = None

    def setup(self, run_dir: Path) -> None:
        """Open domain log files in *run_dir*.  Closes any previously open files."""
        self.close()
        self._run_dir = run_dir
        for domain in self._DOMAINS:
            self._writers[domain] = open(
                run_dir / f"{domain}.log", "a", encoding="utf-8", buffering=1
            )

    def emit(self, domain: str, event_type: str, **fields: object) -> None:
        """Write one structured line to *domain*.log.

        Silently no-ops when the bus has not been set up or the domain
        is unknown — callers must never crash because of logging.
        """
        writer = self._writers.get(domain)
        if writer is None:
            return
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        kv = " ".join(f"{k}={v}" for k, v in fields.items())
        writer.write(f"{ts} | {domain:<6} | {event_type:<18} | {kv}\n")

    def write_raw(self, subdir: str, filename: str, content: str) -> None:
        """Write *content* to *run_dir/subdir/filename*.  Creates dirs as needed."""
        if self._run_dir is None:
            return
        raw_dir = self._run_dir / subdir
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / filename).write_text(content, encoding="utf-8")

    def close(self) -> None:
        """Flush and close all open domain log files."""
        for w in self._writers.values():
            try:
                w.close()
            except Exception:
                pass
        self._writers.clear()


_bus = EventBus()


def get_event_bus() -> EventBus:
    """Return the process-global EventBus singleton."""
    return _bus
