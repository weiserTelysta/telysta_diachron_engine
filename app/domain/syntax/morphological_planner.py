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

        # Collect particles: in analytic domains (state 0) grammaticalized
        # function words surface as independent tokens instead of affixes.
        # Also fires in fully isolating languages for backward compatibility.
        ms = self._typ.morph_state
        has_analytic_domain = (
            ms.verb_tam == 0
            or ms.verb_agreement == 0
            or ms.noun_case == 0
            or self._typ.morph_type == "isolating"
        )
        if has_analytic_domain:
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
        fp = self._typ.feature_presence
        ms = self._typ.morph_state

        if fp.case and self._typ.case_system != "none" and ms.noun_case > 0:
            if ms.noun_case == 2 and self._port is not None:
                # Fusional: try portmanteau lookup first
                fused = self._port.lookup(frozenset({case_key}))
                if fused is not None:
                    suffixes.append(fused.surface_form)
                else:
                    suf = self._typ.get_suffix(case_key)
                    if suf:
                        suffixes.append(suf)
            else:
                # Agglutinative (state 1): transparent suffix
                suf = self._typ.get_suffix(case_key)
                if suf:
                    suffixes.append(suf)
            # state 0: no word-internal case marking (handled by word order / adpositions)

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

        fp = self._typ.feature_presence
        ms = self._typ.morph_state
        prefixes: list[str] = []
        suffix_items: list[tuple[str, str]] = []

        tense = node.attributes.get("tense", "")
        aspect = node.attributes.get("aspect", "")

        # TAM morphology — only attach when domain state > 0
        if ms.verb_tam > 0 and self._typ.tense_system == "inflectional":
            tam_keys = [k for k in [tense, aspect] if k and (
                (k == tense and fp.tense) or (k == aspect and fp.aspect)
            )]
            for gram_key in tam_keys:
                pre = self._typ.get_prefix(gram_key)
                if pre:
                    prefixes.append(pre)
                suf = self._typ.get_suffix(gram_key)
                if suf:
                    suffix_items.append((gram_key, suf))

        # Agreement morphology — only attach when domain state > 0
        if ms.verb_agreement > 0 and fp.agreement and self._typ.agreement_features:
            person = board.read_or("person", "3")
            number = board.read_or("number", "sg")
            agr_key = f"{person}{number.upper()}"
            agr = self._typ.get_suffix(agr_key)
            if agr:
                suffix_items.append((agr_key, agr))

        # Portmanteau fusion: always check pre-registered entries when a
        # registry exists; automatic fusion (maybe_fuse) only fires at state 2
        suffixes = self._fuse_suffixes(suffix_items) if self._port and suffix_items else [ipa for _, ipa in suffix_items]

        return PlannedWord(
            role="verb",
            lexeme_ipa=entity.ipa_current,
            prefixes=prefixes,
            suffixes=suffixes,
            pos=entity.pos,
        )

    def _fuse_suffixes(self, items: list[tuple[str, str]]) -> list[str]:
        """Replace adjacent suffix pairs with portmanteau forms where available.

        ``items`` is a list of (function_key, ipa) pairs, e.g. [("PAST","et"),("1SG","m")].
        Co-occurrence is tracked by function key; lookup and maybe_fuse also use keys.

        Pre-registered portmanteau entries are always checked (lookup).
        Automatic fusion (maybe_fuse) only fires when at least one contributing
        verb domain is at fusional state (2), preventing premature fusion in
        purely agglutinative systems.
        """
        if self._port is None or len(items) < 2:
            return [ipa for _, ipa in items]

        ms = self._typ.morph_state
        allow_auto_fuse = ms.verb_tam == 2 or ms.verb_agreement == 2
        existing_values = set(self._typ.morpheme_table.values())
        result: list[str] = []
        i = 0
        while i < len(items):
            if i + 1 < len(items):
                key_a, ipa_a = items[i]
                key_b, ipa_b = items[i + 1]
                self._port.track_cooccurrence(key_a, key_b)
                fused = self._port.lookup(frozenset({key_a, key_b}))
                if fused is None and allow_auto_fuse:
                    fused = self._port.maybe_fuse(key_a, ipa_a, key_b, ipa_b, existing_values)
                    if fused is not None:
                        combined_key = f"{key_a}+{key_b}"
                        self._typ.morpheme_table[combined_key] = fused.surface_form
                        existing_values.add(fused.surface_form)
                if fused is not None:
                    result.append(fused.surface_form)
                    i += 2
                    continue
            result.append(items[i][1])
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
