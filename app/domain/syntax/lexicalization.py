from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.syntax.semantic_graph import SemanticGraph

if TYPE_CHECKING:
    from app.domain.lexicon.models import LexicalEntity
    from app.domain.storage.hot_state import EngineHotState


class LexicalizationLayer:
    """Maps SemanticPrime IDs → alive LexicalEntity at a given era.

    Lookup strategy (in order):
    1. Exact match on entity.concept == prime_id (case-insensitive).
    2. Ancestor walk: find any prime that IS an ancestor of prime_id in the
       SemanticGraph and whose concept exists in the lexicon.
    3. Return None if no candidate survives.

    Only alive (not is_dead) words are considered.
    """

    def __init__(self, prime_graph: SemanticGraph) -> None:
        self._primes = prime_graph

    def lexicalize(
        self,
        hot_state: "EngineHotState",
        era: int | None = None,
    ) -> dict[str, "LexicalEntity | None"]:
        """Return {prime_id → LexicalEntity | None} for all known primes."""
        alive = {
            e.concept.upper(): e
            for e in hot_state.lexicon.values()
            if not e.is_dead
        }
        result: dict[str, "LexicalEntity | None"] = {}
        for prime in self._primes:
            result[prime.id] = self._resolve(prime.id, alive)
        return result

    def lexicalize_one(
        self,
        prime_id: str,
        hot_state: "EngineHotState",
    ) -> "LexicalEntity | None":
        alive = {
            e.concept.upper(): e
            for e in hot_state.lexicon.values()
            if not e.is_dead
        }
        return self._resolve(prime_id, alive)

    def _resolve(
        self,
        prime_id: str,
        alive: dict[str, "LexicalEntity"],
    ) -> "LexicalEntity | None":
        if prime_id in alive:
            return alive[prime_id]

        for ancestor_id in self._primes.ancestors(prime_id):
            if ancestor_id in alive:
                return alive[ancestor_id]

        return None
