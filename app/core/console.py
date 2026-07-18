"""TUI progress reporter — the sole writer to stdout.

Implements "silent step + checkpoint report" mode:
  - Each era prints one character (.  !  ?) on a single line
  - Only epoch boundaries and the final summary produce full lines
  - Warnings/errors from the logger framework are the only other stdout output

Character legend:
  .  normal era
  !  massive sound change  (changed_count > 10% of alive words)
  ?  typology drift        (morph_type changed this era)
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.lexicon.models import LexicalEntity

_BOLD = "\033[1m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"

_PREFIX_W = 26  # fixed column width for the epoch prefix

# --------------------------------------------------------------------------
# Module-level state (reset at session_start / epoch_start)
# --------------------------------------------------------------------------
_notable: list[tuple[int, str]] = []
_era_stride: int = 1
_era_counter: int = 0
_t0: float = 0.0


def _ensure_utf8_stream(stream: object) -> None:
    """Use UTF-8 when the host stream supports runtime reconfiguration.

    Windows commonly starts Python with a legacy console encoding such as
    GBK. IPA symbols outside that code page would otherwise crash the CLI at
    the final summary even though the evolution itself completed.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    encoding = str(getattr(stream, "encoding", "") or "").lower().replace("-", "")
    if encoding == "utf8":
        return
    try:
        reconfigure(encoding="utf-8")
    except (OSError, ValueError):
        # Redirected and test streams may reject reconfiguration. They usually
        # accept Unicode strings directly, so console reporting can continue.
        return


def session_start(seed: int, preset: str) -> None:
    global _t0
    _ensure_utf8_stream(sys.stdout)
    _ensure_utf8_stream(sys.stderr)
    _t0 = time.monotonic()
    print(f"{_BOLD}[SEED: {seed}]{_RESET} Evolution Started — preset={preset}")


def epoch_start(idx: int, total: int, name: str, era_count: int) -> None:
    global _notable, _era_stride, _era_counter
    _notable = []
    _era_stride = max(1, era_count // 40)
    _era_counter = 0
    prefix = f"[Epoch {idx}/{total}: {name}]"
    print(f"{_CYAN}{prefix:<{_PREFIX_W}}{_RESET} ", end="", flush=True)


def era_dot(era: int, notable: str = "") -> None:
    global _era_counter
    _era_counter += 1
    if notable:
        _notable.append((era, notable))
    if _era_counter % _era_stride == 0:
        marker = notable if notable else "."
        color = _YELLOW if notable else ""
        reset = _RESET if notable else ""
        print(f"{color}{marker}{reset}", end="", flush=True)


def epoch_end(alive: int, morph: str, order: str) -> None:
    notes = ""
    if _notable:
        parts = []
        for era, marker in _notable[:3]:
            label = "ΔSound>10%" if marker == "!" else "TypologyShift"
            parts.append(f"{marker} Era{era}:{label}")
        notes = f"  ({', '.join(parts)})"
    print(f" {_GREEN}[OK]{_RESET} Alive: {alive} | {order} | {morph}{notes}")


def session_end(
    total_eras: int,
    alive: int,
    dead: int,
    morph: str,
    order: str,
    sample: str = "",
) -> None:
    elapsed = time.monotonic() - _t0
    sample_line = f"\nSample: {sample}" if sample else ""
    print(
        f"\n{_BOLD}{_GREEN}[FINISH]{_RESET}"
        f" {total_eras} Eras in {elapsed:.2f}s"
        f"  |  Alive: {alive}  Dead: {dead}"
        f"  morph={morph}{sample_line}"
    )


def demo_line(msg: str) -> None:
    """Print a single demo/summary line to stdout."""
    print(msg, flush=True)
