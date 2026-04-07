from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from app.domain.lexicon.dag import WordDAG

if TYPE_CHECKING:
    from app.domain.lexicon.models import LexicalEntity
    from app.domain.storage.event_log import DeltaEvent


class EngineHotState:
    """In-memory current-era word table.

    All evolution computation operates exclusively on this object.
    The persistent layer (DeltaEvent / KeyframeManager) is a write-only
    side-effect — it never blocks or influences computation here.

    Rule: compute → write Hot State → fire delta event (async write).
    """

    def __init__(
        self,
        lexicon: dict[str, "LexicalEntity"] | None = None,
        current_era: int = 0,
        dag: WordDAG | None = None,
        swadesh_concepts: set[str] | None = None,
    ) -> None:
        self.lexicon: dict[str, "LexicalEntity"] = lexicon or {}
        self.current_era: int = current_era
        self.dag: WordDAG = dag if dag is not None else WordDAG()
        # Concept names protected from hard-deletion (Swadesh core vocabulary)
        self.swadesh_concepts: set[str] = swadesh_concepts or set()

    def load_entities(self, entities: list["LexicalEntity"]) -> None:
        self.lexicon = {e.id: e for e in entities}
        for e in entities:
            self.dag.add_node(e.id)

    def get(self, word_id: str) -> "LexicalEntity | None":
        return self.lexicon.get(word_id)

    def put(self, entity: "LexicalEntity") -> None:
        self.lexicon[entity.id] = entity
        self.dag.add_node(entity.id)

    def all_alive(self) -> list["LexicalEntity"]:
        return [e for e in self.lexicon.values() if not e.is_dead]

    # ------------------------------------------------------------------
    # User-facing insert / delete with Swadesh guard
    # ------------------------------------------------------------------

    def insert_word(self, entity: "LexicalEntity", era: int) -> "DeltaEvent":
        """Inject a new word into the lexicon and return the corresponding DeltaEvent.

        Sets era_born to current era if not already set.
        """
        from app.domain.storage.event_log import DeltaEvent, DeltaEventType

        if not entity.era_born:
            entity.era_born = era
        self.put(entity)
        return DeltaEvent(
            event_type=DeltaEventType.INJECT_WORD,
            era=era,
            word_id=entity.id,
            new_entity=entity,
        )

    def delete_word(self, word_id: str, era: int) -> "DeltaEvent":
        """Soft-delete a word (is_dead = True) and return the corresponding DeltaEvent.

        Raises ValueError if the word's concept is in swadesh_concepts (protected).
        """
        from app.domain.storage.event_log import DeltaEvent, DeltaEventType

        entity = self.lexicon.get(word_id)
        if entity is None:
            raise KeyError(f"Word not found: {word_id!r}")
        if entity.concept in self.swadesh_concepts:
            raise ValueError(
                f"Cannot delete Swadesh core word: {entity.concept!r} ({word_id})"
            )
        entity.is_dead = True
        return DeltaEvent(
            event_type=DeltaEventType.MARK_DEAD,
            era=era,
            word_id=word_id,
        )

    # ------------------------------------------------------------------
    # Delta application
    # ------------------------------------------------------------------

    def apply_delta(self, event: "DeltaEvent") -> None:
        """Update Hot State in response to a DeltaEvent."""
        from app.domain.storage.event_log import DeltaEventType

        if event.event_type == DeltaEventType.SOUND_CHANGE:
            entity = self.lexicon.get(event.word_id)
            if entity and event.new_ipa:
                entity.ipa_history.append(entity.ipa_current)
                entity.ipa_current = event.new_ipa
                if event.dag_parent_id:
                    self.dag.add_edge(
                        event.dag_parent_id, event.word_id, event.era, "sound_change"
                    )

        elif event.event_type == DeltaEventType.MARK_DEAD:
            entity = self.lexicon.get(event.word_id)
            if entity:
                entity.is_dead = True

        elif event.event_type in (
            DeltaEventType.INJECT_WORD,
            DeltaEventType.BORROW_WORD,
            DeltaEventType.FOSSIL_SPAWN,
        ):
            if event.new_entity:
                self.lexicon[event.new_entity.id] = event.new_entity
                self.dag.add_node(event.new_entity.id)
                if event.dag_parent_id:
                    edge_type = (
                        "borrowing" if event.event_type == DeltaEventType.BORROW_WORD
                        else "fossil_prefix" if event.event_type == DeltaEventType.FOSSIL_SPAWN
                        else "sound_change"
                    )
                    self.dag.add_edge(
                        event.dag_parent_id, event.new_entity.id, event.era, edge_type
                    )

        elif event.event_type == DeltaEventType.DAG_EDGE_ADD:
            if event.dag_parent_id and event.word_id and event.edge_type:
                self.dag.add_edge(
                    event.dag_parent_id,
                    event.word_id,
                    event.era,
                    event.edge_type,  # type: ignore[arg-type]
                )

        elif event.event_type == DeltaEventType.ERA_ADVANCE:
            self.current_era = event.era

    # ------------------------------------------------------------------
    # Snapshot / clone
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """Return a full serializable dict of the current state."""
        from dataclasses import asdict
        return {
            "era": self.current_era,
            "lexicon": {wid: asdict(e) for wid, e in self.lexicon.items()},
            "dag": self.dag.to_dict(),
        }

    def clone(self) -> "EngineHotState":
        """Deep-copy the state for read-only historical reconstruction."""
        return EngineHotState(
            lexicon=copy.deepcopy(self.lexicon),
            current_era=self.current_era,
            dag=WordDAG.from_dict(self.dag.to_dict()),
            swadesh_concepts=set(self.swadesh_concepts),
        )

    def __len__(self) -> int:
        return len(self.lexicon)

    def __repr__(self) -> str:
        return f"EngineHotState(era={self.current_era}, words={len(self.lexicon)})"
