from __future__ import annotations

import logging
from dataclasses import fields
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.storage.event_log import KeyframeManager
    from app.domain.storage.hot_state import EngineHotState

logger = logging.getLogger(__name__)


class HistoryRebuilder:
    """Read-only historical state reconstruction.

    Algorithm:
      1. Find the nearest keyframe era ≤ target_era.
      2. Load that keyframe snapshot into a cloned EngineHotState.
      3. Replay all DeltaEvents from keyframe_era+1 to target_era.
      4. Return the reconstructed state.

    This operation is entirely read-only and never touches the live Hot State.
    """

    def __init__(self, keyframe_manager: "KeyframeManager") -> None:
        self.km = keyframe_manager

    def rebuild(self, target_era: int) -> "EngineHotState":
        from app.domain.lexicon.models import LexicalEntity
        from app.domain.storage.event_log import DeltaEvent, DeltaEventType
        from app.domain.storage.hot_state import EngineHotState

        nearest_kf_era = self.km.find_nearest_keyframe_era(target_era)
        kf_snapshot = self.km.load_keyframe(nearest_kf_era)

        if kf_snapshot is None:
            logger.warning("No keyframe found for era %d, returning empty state", nearest_kf_era)
            return EngineHotState(current_era=target_era)

        state = self._load_snapshot(kf_snapshot)

        for era in range(nearest_kf_era + 1, target_era + 1):
            delta_dicts = self.km.load_deltas_for_era(era)
            for d in delta_dicts:
                event = self._dict_to_event(d)
                state.apply_delta(event)

        state.current_era = target_era
        return state

    def _load_snapshot(self, snapshot: dict) -> "EngineHotState":
        from app.domain.lexicon.models import LexicalEntity
        from app.domain.storage.hot_state import EngineHotState

        era = snapshot.get("era", 0)
        lexicon_raw: dict[str, dict] = snapshot.get("lexicon", {})

        field_names = {f.name for f in fields(LexicalEntity)}
        lexicon: dict[str, LexicalEntity] = {}
        for wid, entry in lexicon_raw.items():
            filtered = {k: v for k, v in entry.items() if k in field_names}
            lexicon[wid] = LexicalEntity(**filtered)

        return EngineHotState(lexicon=lexicon, current_era=era)

    def _dict_to_event(self, d: dict) -> "DeltaEvent":
        from app.domain.storage.event_log import DeltaEvent, DeltaEventType

        entity = None
        if d.get("new_entity"):
            from app.domain.lexicon.models import LexicalEntity
            from dataclasses import fields as dc_fields
            field_names = {f.name for f in dc_fields(LexicalEntity)}
            filtered = {k: v for k, v in d["new_entity"].items() if k in field_names}
            entity = LexicalEntity(**filtered)

        return DeltaEvent(
            event_type=DeltaEventType(d["event_type"]),
            era=d["era"],
            word_id=d.get("word_id", ""),
            new_ipa=d.get("new_ipa"),
            old_ipa=d.get("old_ipa"),
            new_entity=entity,
            rule_name=d.get("rule_name", ""),
            timestamp=d.get("timestamp", ""),
        )
