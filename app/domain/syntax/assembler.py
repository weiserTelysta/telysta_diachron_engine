from __future__ import annotations

import random
from collections import defaultdict

from app.domain.lexicon.models import LexicalEntity
from app.core.rng import RngTree

_POS_GROUPS: dict[str, list[str]] = {
    "noun": ["n.", "n"],
    "verb": ["v.", "v"],
    "adj":  ["adj.", "adj"],
    "adv":  ["adv.", "adv"],
    "pron": ["pron.", "pron"],
    "other": [],
}

_TEMPLATES: list[list[str]] = [
    ["pron",  "verb"],
    ["noun",  "verb"],
    ["pron",  "verb",  "noun"],
    ["noun",  "verb",  "noun"],
    ["pron",  "verb",  "adj"],
    ["noun",  "adj"],
    ["verb",  "noun"],
]


class SentenceAssembler:
    """Phase 0 proto-sentence assembler: pure IPA concatenation, no morphology.

    Groups lexical entities by broad POS category and randomly selects
    words according to simple clause templates. Words are joined with
    spaces. No grammatical agreement or morphological change is applied.
    """

    def __init__(self, entities: list[LexicalEntity]) -> None:
        self._groups: dict[str, list[LexicalEntity]] = defaultdict(list)
        for e in entities:
            if e.is_dead:
                continue
            group = self._pos_group(e.pos)
            self._groups[group].append(e)
        if not self._groups.get("pron"):
            self._groups["pron"] = self._groups.get("noun", [])

    @staticmethod
    def _pos_group(pos: str) -> str:
        pos_lower = pos.lower().strip()
        for group, tags in _POS_GROUPS.items():
            if group == "other":
                continue
            if any(pos_lower == t.lower() or pos_lower.startswith(t.lower()) for t in tags):
                return group
        return "other"

    def _pick(self, group: str, rng: random.Random) -> LexicalEntity | None:
        pool = self._groups.get(group) or self._groups.get("other") or []
        if not pool:
            return None
        return rng.choice(pool)

    def assemble(self, n: int = 10, rng: random.Random | None = None) -> list[str]:
        """Return `n` proto-sentences as IPA strings."""
        if rng is None:
            rng = RngTree(0).python("syntax", "assembler")

        templates = [t for t in _TEMPLATES if all(
            self._groups.get(role) for role in t
        )]
        if not templates:
            templates = [["noun"], ["verb"]]

        sentences: list[str] = []
        for _ in range(n):
            template = rng.choice(templates)
            parts: list[str] = []
            for role in template:
                word = self._pick(role, rng)
                if word:
                    parts.append(word.ipa_current)
            if parts:
                sentences.append(" ".join(parts))
        return sentences
