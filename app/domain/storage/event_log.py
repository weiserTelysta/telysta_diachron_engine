from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.lexicon.models import LexicalEntity

logger = logging.getLogger(__name__)


class DeltaEventType(str, Enum):
    SOUND_CHANGE = "sound_change"
    MARK_DEAD = "mark_dead"
    INJECT_WORD = "inject_word"
    ERA_ADVANCE = "era_advance"
    EXEMPLAR_UPDATE = "exemplar_update"
    BORROW_WORD = "borrow_word"       # 跨语言借词注入
    FOSSIL_SPAWN = "fossil_spawn"     # 化石前缀生成
    DAG_EDGE_ADD = "dag_edge_add"     # 显式 DAG 边记录


@dataclass
class DeltaEvent:
    event_type: DeltaEventType
    era: int
    word_id: str = ""
    new_ipa: str | None = None
    old_ipa: str | None = None
    new_entity: "LexicalEntity | None" = field(default=None, repr=False)
    rule_name: str = ""
    dag_parent_id: str = ""           # BORROW_WORD / FOSSIL_SPAWN 的父词 ID
    source_language: str = ""         # BORROW_WORD 来源语言名
    edge_type: str = ""               # DAG_EDGE_ADD 的边类型
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.new_entity is not None:
            d["new_entity"] = asdict(self.new_entity)
        return d


class KeyframeManager:
    """Manages Delta event log and periodic full-state keyframes.

    Write model:
      - Each DeltaEvent is appended to the current era's log file immediately.
      - Every `keyframe_interval` eras, a full snapshot is written.

    Read model (history reconstruction):
      - Find the nearest preceding keyframe.
      - Replay Delta events up to the target era.
      - This is read-only and never affects Hot State.
    """

    def __init__(
        self,
        base_dir: str | Path,
        keyframe_interval: int = 10,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.keyframe_interval = keyframe_interval
        self._delta_buffer: list[DeltaEvent] = []
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def record(self, event: DeltaEvent) -> None:
        """Buffer a delta event in memory. Call flush_era() at era boundary to persist."""
        self._delta_buffer.append(event)

    def flush_era(self, era: int) -> None:
        """Batch-write all buffered events for `era` to disk in one IO operation.

        O(N) single write replaces the previous O(N²) read-append-write per event.
        Must be called once at the end of each era loop in the evolution pipeline.
        """
        era_events = [e for e in self._delta_buffer if e.era == era]
        if era_events:
            path = self._delta_path(era)
            with open(path, "w", encoding="utf-8") as f:
                json.dump([e.to_dict() for e in era_events], f, ensure_ascii=False, indent=2)
            logger.info("Delta flushed: era=%d events=%d → %s", era, len(era_events), path)
        self._delta_buffer = [e for e in self._delta_buffer if e.era != era]

    def write_keyframe(self, era: int, snapshot: dict) -> None:
        path = self.base_dir / f"keyframe_era_{era:04d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        logger.info("Keyframe written: %s", path)

    def should_write_keyframe(self, era: int) -> bool:
        return era % self.keyframe_interval == 0

    def load_keyframe(self, era: int) -> dict | None:
        path = self.base_dir / f"keyframe_era_{era:04d}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def load_deltas_for_era(self, era: int) -> list[dict]:
        path = self._delta_path(era)
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def find_nearest_keyframe_era(self, target_era: int) -> int:
        """Return the largest keyframe era ≤ target_era, or 0."""
        best = 0
        for kf in self.base_dir.glob("keyframe_era_*.json"):
            era_str = kf.stem.replace("keyframe_era_", "")
            try:
                era_num = int(era_str)
            except ValueError:
                continue
            if era_num <= target_era:
                best = max(best, era_num)
        return best

    def _delta_path(self, era: int) -> Path:
        return self.base_dir / f"delta_era_{era:04d}.json"
