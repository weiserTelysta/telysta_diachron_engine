from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.domain.syntax.feature_blackboard import FeatureBlackboard
from app.domain.syntax.typology import TypologyMatrix

if TYPE_CHECKING:
    from app.domain.lexicon.models import LexicalEntity
    from app.domain.morphology.portmanteau import PortmanteauRegistry
    from app.domain.syntax.csg import ControlledSemanticGraph


@dataclass
class PlannedWord:
    """A lexicalized word ready for linearization, with all affixes attached."""

    role: str
    lexeme_ipa: str
    prefixes: list[str] = field(default_factory=list)
    suffixes: list[str] = field(default_factory=list)
    pos: str = ""

    @property
    def surface_ipa(self) -> str:
        return "".join(self.prefixes) + self.lexeme_ipa + "".join(self.suffixes)


class MorphologicalPlanner:
    """Maps CSG + lexicalization result to a list of PlannedWord.

    Decision strategy (in priority order):
    1. Find predicate, agent, patient from CSG edge structure.
    2. Write agent's person/number to FeatureBlackboard for Agreement.
    3. Attach case suffixes to subject/object per case_system.
    4. Attach tense/aspect morpheme to verb per tense_system.
    5. Check PortmanteauRegistry for fused endings before concatenating.
    6. Attach agreement suffix to verb if agreement_features is non-empty.

    Edge convention in CSG:
    - ``FROM →[agent]→ TO``: FROM is the agent, TO is the predicate.
    - ``FROM →[patient]→ TO``: FROM is the predicate, TO is the patient.
    - ``FROM →[modifier]→ TO``: FROM modifies TO.

    When typology.morph_type == "isolating", grammaticalized function words
    that carry the ``word_class="function"`` flag are planned as ``"particle"``
    role entries rather than being attached as affixes.
    """

    def __init__(
        self,
        typology: TypologyMatrix,
        portmanteau_registry: "PortmanteauRegistry | None" = None,
    ) -> None:
        self._typ = typology
        self._port = portmanteau_registry

    def plan(
        self,
        csg: "ControlledSemanticGraph",
        lexmap: dict[str, "LexicalEntity | None"],
        board: FeatureBlackboard,
    ) -> list[PlannedWord]:
        board.clear()

        agent_id = self._edge_from("agent", csg)
        pred_id = self._edge_to("agent", csg) or self._edge_from("patient", csg)
        patient_id = self._edge_to("patient", csg)

        self._populate_blackboard(agent_id, csg, board)

        planned: list[PlannedWord] = []

        if agent_id is not None:
            pw = self._plan_nominal(agent_id, "subject", "NOM", csg, lexmap)
            if pw is not None:
                planned.append(pw)

        if pred_id is not None:
            pw = self._plan_verb(pred_id, csg, lexmap, board)
            if pw is not None:
                planned.append(pw)

        if patient_id is not None:
            case_key = "ABS" if self._typ.case_system == "ergative_absolutive" else "ACC"
            pw = self._plan_nominal(patient_id, "object", case_key, csg, lexmap)
            if pw is not None:
                planned.append(pw)

        for edge in csg.edges:
            if edge.relation == "modifier":
                pw = self._plan_modifier(edge.from_id, csg, lexmap)
                if pw is not None:
                    planned.append(pw)

        if self._typ.morph_type == "isolating":
            for pw in self._plan_particles(lexmap):
                planned.append(pw)

        return planned

    def _edge_from(
        self, relation: str, csg: "ControlledSemanticGraph"
    ) -> str | None:
        for edge in csg.edges:
            if edge.relation == relation:
                return edge.from_id
        return None

    def _edge_to(
        self, relation: str, csg: "ControlledSemanticGraph"
    ) -> str | None:
        for edge in csg.edges:
            if edge.relation == relation:
                return edge.to_id
        return None

    def _populate_blackboard(
        self,
        agent_id: str | None,
        csg: "ControlledSemanticGraph",
        board: FeatureBlackboard,
    ) -> None:
        if agent_id is None:
            return
        node = csg.get_node(agent_id)
        if node is None:
            return
        board.write("person", node.attributes.get("person", "3"))
        board.write("number", node.attributes.get("number", "sg"))

    def _plan_nominal(
        self,
        node_id: str,
        role: str,
        case_key: str,
        csg: "ControlledSemanticGraph",
        lexmap: dict[str, "LexicalEntity | None"],
    ) -> PlannedWord | None:
        node = csg.get_node(node_id)
        if node is None:
            return None
        entity = lexmap.get(node.prime_id)
        if entity is None:
            return None

        suffixes: list[str] = []
        if self._typ.case_system != "none":
            suf = self._typ.get_suffix(case_key)
            if suf:
                suffixes.append(suf)

        return PlannedWord(
            role=role,
            lexeme_ipa=entity.ipa_current,
            suffixes=suffixes,
            pos=entity.pos,
        )

    def _plan_verb(
        self,
        node_id: str,
        csg: "ControlledSemanticGraph",
        lexmap: dict[str, "LexicalEntity | None"],
        board: FeatureBlackboard,
    ) -> PlannedWord | None:
        node = csg.get_node(node_id)
        if node is None:
            return None
        entity = lexmap.get(node.prime_id)
        if entity is None:
            return None

        prefixes: list[str] = []
        suffixes: list[str] = []

        tense = node.attributes.get("tense", "")
        aspect = node.attributes.get("aspect", "")

        if self._typ.tense_system == "inflectional":
            for gram_key in filter(None, [tense, aspect]):
                pre = self._typ.get_prefix(gram_key)
                if pre:
                    prefixes.append(pre)
                suf = self._typ.get_suffix(gram_key)
                if suf:
                    suffixes.append(suf)
        elif self._typ.tense_system == "isolating":
            pass

        if self._typ.agreement_features:
            person = board.read_or("person", "3")
            number = board.read_or("number", "sg")
            agr_key = f"{person}{number.upper()}"
            agr = self._typ.get_suffix(agr_key)
            if agr:
                suffixes.append(agr)

        if self._port and suffixes:
            suffixes = self._fuse_suffixes(suffixes)

        return PlannedWord(
            role="verb",
            lexeme_ipa=entity.ipa_current,
            prefixes=prefixes,
            suffixes=suffixes,
            pos=entity.pos,
        )

    def _fuse_suffixes(self, suffixes: list[str]) -> list[str]:
        """Replace adjacent suffix pairs with portmanteau forms where available.

        Iterates left-to-right; on a match, replaces the pair with the fused
        surface form and continues from the next unmatched suffix. Also tracks
        co-occurrences for future automatic fusion via maybe_fuse.
        """
        if self._port is None or len(suffixes) < 2:
            return suffixes

        result: list[str] = []
        i = 0
        while i < len(suffixes):
            if i + 1 < len(suffixes):
                key_a = suffixes[i]
                key_b = suffixes[i + 1]
                self._port.track_cooccurrence(key_a, key_b)
                fused = self._port.lookup(frozenset({key_a, key_b}))
                if fused is not None:
                    result.append(fused.surface_form)
                    i += 2
                    continue
            result.append(suffixes[i])
            i += 1
        return result

    def _plan_particles(
        self,
        lexmap: dict[str, "LexicalEntity | None"],
    ) -> list[PlannedWord]:
        """Collect function-word particles for isolating-language output.

        In isolating typology, grammaticalized function words (word_class="function",
        grammaticalization_stage >= 2) appear as independent syntactic tokens
        (particles) rather than as affixes. This implements the Sino-Tibetan route
        where grammaticalized content words become free particles (了, 在, 把…).
        """
        particles: list[PlannedWord] = []
        for entity in lexmap.values():
            if entity is None:
                continue
            if (
                entity.word_class == "function"
                and entity.grammaticalization_stage >= 2
                and entity.grammatical_function
                and entity.ipa_current
            ):
                particles.append(
                    PlannedWord(
                        role="particle",
                        lexeme_ipa=entity.ipa_current,
                        pos=entity.pos,
                    )
                )
        return particles

    def _plan_modifier(
        self,
        node_id: str,
        csg: "ControlledSemanticGraph",
        lexmap: dict[str, "LexicalEntity | None"],
    ) -> PlannedWord | None:
        node = csg.get_node(node_id)
        if node is None:
            return None
        entity = lexmap.get(node.prime_id)
        if entity is None:
            return None
        return PlannedWord(
            role="modifier",
            lexeme_ipa=entity.ipa_current,
            pos=entity.pos,
        )
