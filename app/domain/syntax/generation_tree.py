from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.domain.syntax.typology import TypologyMatrix

if TYPE_CHECKING:
    from app.domain.syntax.morphological_planner import PlannedWord

_ROLE_TO_SLOT: dict[str, str] = {
    "subject": "S",
    "verb": "V",
    "object": "O",
}

_ALL_ORDERS: dict[str, list[str]] = {
    "SOV": ["S", "O", "V"],
    "SVO": ["S", "V", "O"],
    "VSO": ["V", "S", "O"],
    "VOS": ["V", "O", "S"],
    "OVS": ["O", "V", "S"],
    "OSV": ["O", "S", "V"],
}


@dataclass
class GenerationNode:
    """A word in the generation tree, tagged with its syntactic role."""

    word: "PlannedWord"
    syntactic_slot: str

    @property
    def surface_ipa(self) -> str:
        return self.word.surface_ipa


class GenerationTree:
    """Ordered sequence of GenerationNode, linearizable by word order.

    Build via :meth:`from_planned`, then call :meth:`linearize` to get
    the final IPA token list ordered by the typology's word order scheme.

    Modifier nodes are placed immediately before the node they modify
    (head-final default); this is the simplest cross-linguistically common
    strategy and sufficient for Phase 3 baseline.
    """

    def __init__(self) -> None:
        self._nodes: list[GenerationNode] = []

    def append(self, node: GenerationNode) -> None:
        self._nodes.append(node)

    @property
    def nodes(self) -> list[GenerationNode]:
        return list(self._nodes)

    @classmethod
    def from_planned(
        cls,
        typology: TypologyMatrix,
        words: list["PlannedWord"],
    ) -> "GenerationTree":
        tree = cls()
        slot_order = _ALL_ORDERS.get(typology.word_order, ["S", "V", "O"])

        core_nodes: dict[str, GenerationNode] = {}
        modifier_nodes: list[GenerationNode] = []

        for word in words:
            slot = _ROLE_TO_SLOT.get(word.role)
            if slot is not None:
                core_nodes[slot] = GenerationNode(word=word, syntactic_slot=slot)
            elif word.role == "modifier":
                modifier_nodes.append(GenerationNode(word=word, syntactic_slot="MOD"))

        particle_nodes: list[GenerationNode] = []
        for word in words:
            if word.role == "particle":
                particle_nodes.append(GenerationNode(word=word, syntactic_slot="PAR"))

        for slot in slot_order:
            node = core_nodes.get(slot)
            if node is not None:
                for mod in modifier_nodes:
                    tree.append(mod)
                modifier_nodes.clear()
                tree.append(node)
                if slot == "V":
                    for par in particle_nodes:
                        tree.append(par)
                    particle_nodes.clear()

        for mod in modifier_nodes:
            tree.append(mod)
        for par in particle_nodes:
            tree.append(par)

        return tree

    def linearize(self) -> list[str]:
        """Return surface IPA tokens in sentence order."""
        return [n.surface_ipa for n in self._nodes if n.surface_ipa]
