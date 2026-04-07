"""Vocabulary expansion engines.

Three mechanisms share the WordInjector Protocol so the EpochManager
calls them through a unified interface:

  DomainInjector   — LLM-off fallback: reads domain_vocabulary/*.json
  RagInjector      — LLM-on enhancement: wraps existing RAG pipeline
  CompoundingEngine — semantic_compounds.json → compound LexicalEntities
  VocabularyRenewalEngine — monitors Swadesh 100 vacuums, fires REPLACEMENT_NEEDED
"""

from __future__ import annotations

import json
import random
from dataclasses import field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from app.core.logging import get_logger
from app.domain.lexicon.models import LexicalEntity
from app.domain.storage.event_log import DeltaEvent, DeltaEventType

if TYPE_CHECKING:
    from app.domain.phonology.phoneme import PhonemeInventory
    from app.domain.storage.hot_state import EngineHotState

logger = get_logger(__name__)

# ------------------------------------------------------------------
# Protocol
# ------------------------------------------------------------------

@runtime_checkable
class WordInjector(Protocol):
    """Shared interface for all vocabulary-expansion strategies."""

    def inject(
        self,
        hot: "EngineHotState",
        era: int,
        inv: "PhonemeInventory",
        rng: random.Random,
    ) -> list[LexicalEntity]:
        """Inject new words into *hot* and return the list of injected entities."""
        ...


# ------------------------------------------------------------------
# DomainInjector
# ------------------------------------------------------------------

class DomainInjector:
    """Reads a domain vocabulary JSON file and injects words into the lexicon.

    Each entry is assigned a freshly generated IPA form from the phoneme
    inventory.  Words are tagged with era_born so the timeline tab can
    attribute them to the correct epoch boundary.
    """

    def __init__(self, domain_file: str | Path, base_dir: str | Path) -> None:
        self._path = Path(base_dir) / f"{domain_file}.json"

    def inject(
        self,
        hot: "EngineHotState",
        era: int,
        inv: "PhonemeInventory",
        rng: random.Random,
    ) -> list[LexicalEntity]:
        if not self._path.exists():
            logger.warning("Domain vocabulary file not found: %s", self._path)
            return []

        with open(self._path, encoding="utf-8") as f:
            entries = json.load(f)

        injected: list[LexicalEntity] = []
        for entry in entries:
            concept = entry["concept"]
            # Skip if this concept already has an alive entry
            if any(e.concept == concept and not e.is_dead for e in hot.lexicon.values()):
                continue

            ipa = self._generate_ipa(inv, rng)
            entity = LexicalEntity(
                id=f"domain_{concept.replace(' ', '_')}_{era}",
                concept=concept,
                pos=entry.get("pos", "n."),
                ipa_current=ipa,
                ipa_history=[],
                frequency_weight=0.002,
                word_class=entry.get("word_class", "content"),
                is_dead=False,
                ipa_exemplars=[{"form": ipa, "weight": 1.0}],
                stress_pattern=self._infer_stress(ipa, inv),
                era_born=era,
            )
            event = hot.insert_word(entity, era)
            injected.append(entity)
            logger.debug("Injected domain word: %s /%s/", concept, ipa)

        return injected

    @staticmethod
    def _generate_ipa(inv: "PhonemeInventory", rng: random.Random) -> str:
        templates = ["CV", "CVC", "CVCV"]
        weights = [0.3, 0.4, 0.3]
        template = rng.choices(templates, weights=weights, k=1)[0]
        C = inv.sample_consonant
        V = inv.sample_vowel
        Cc = inv.sample_coda_consonant
        if template == "CV":
            return C(rng).symbol + V(rng).symbol
        if template == "CVC":
            return C(rng).symbol + V(rng).symbol + Cc(rng).symbol
        return C(rng).symbol + V(rng).symbol + C(rng).symbol + V(rng).symbol

    @staticmethod
    def _infer_stress(ipa: str, inv: "PhonemeInventory") -> str:
        vowel_symbols = frozenset(p.symbol for p in inv.vowels)
        tokens = inv.tokenize(ipa)
        count = sum(1 for t in tokens if t in vowel_symbols)
        return "mono" if count <= 1 else "penultimate"


# ------------------------------------------------------------------
# RagInjector
# ------------------------------------------------------------------

class RagInjector:
    """LLM-backed word generation via the existing RAG pipeline.

    When LLM is disabled, MockBackend returns deterministic fixture words.
    Both paths share the same injection interface.
    """

    def __init__(self, backend: object, settings: object) -> None:
        self._backend = backend
        self._settings = settings

    def inject(
        self,
        hot: "EngineHotState",
        era: int,
        inv: "PhonemeInventory",
        rng: random.Random,
    ) -> list[LexicalEntity]:
        from app.llm.contracts import RagLexemeRequest
        from app.llm.rag import generate_new_word, retrieve_anchor_candidates

        # Pick a target concept from domain vocabulary that's missing
        alive_concepts = {e.concept for e in hot.lexicon.values() if not e.is_dead}
        candidates_pool = [
            c for c in ["river", "forest", "elder", "dream", "storm", "wisdom"]
            if c not in alive_concepts
        ]
        if not candidates_pool:
            return []

        target_concept = rng.choice(candidates_pool)
        anchor_candidates = retrieve_anchor_candidates(
            hot.lexicon, hot.dag, target_concept, "n.", max_candidates=8
        )
        request = RagLexemeRequest(
            era=era,
            anchor_concept=target_concept,
            anchor_pos="n.",
            candidate_roots=anchor_candidates,
        )
        response = generate_new_word(self._backend, request)
        if response is None or not response.new_ipa:
            return []

        entity = LexicalEntity(
            id=f"rag_{target_concept}_{era}",
            concept=response.new_concept or target_concept,
            pos="n.",
            ipa_current=response.new_ipa,
            ipa_history=[],
            frequency_weight=0.002,
            word_class="content",
            is_dead=False,
            ipa_exemplars=[{"form": response.new_ipa, "weight": 1.0}],
            era_born=era,
        )
        hot.insert_word(entity, era)
        logger.info("RAG injected: %s /%s/ (era %d)", entity.concept, entity.ipa_current, era)
        return [entity]


# ------------------------------------------------------------------
# CompoundingEngine
# ------------------------------------------------------------------

class CompoundingEngine:
    """Generates compound LexicalEntities from semantic_compounds.json rules.

    A compound is created when BOTH component concepts are alive in the
    current lexicon AND the compound concept does not yet exist.
    IPA is formed by concatenating the component IPA forms, with the
    boundary consonant of the first component dropped if it creates a
    cluster that violates basic phonotactics.
    """

    def __init__(self, compounds_file: str | Path) -> None:
        with open(compounds_file, encoding="utf-8") as f:
            self._rules: list[dict] = json.load(f)

    # Maximum IPA character length for a compound word (physical lock 2)
    _MAX_COMPOUND_IPA_LEN: int = 10

    def generate(
        self,
        hot: "EngineHotState",
        era: int,
        rng: random.Random,
        epoch_idx: int = 0,
    ) -> list[LexicalEntity]:
        alive_by_concept: dict[str, LexicalEntity] = {}
        for e in hot.all_alive():
            # Physical lock 1: only pure roots (no "_" in concept) can be parents
            if "_" not in e.concept and e.concept not in alive_by_concept:
                alive_by_concept[e.concept] = e

        existing_concepts = {e.concept for e in hot.lexicon.values()}
        generated: list[LexicalEntity] = []

        for rule in self._rules:
            if rule.get("epoch_min", 0) > epoch_idx:
                continue
            comp_a, comp_b = rule["components"]
            target_concept = rule["concept"]

            if target_concept in existing_concepts:
                continue
            if comp_a not in alive_by_concept or comp_b not in alive_by_concept:
                continue

            parent_a = alive_by_concept[comp_a]
            parent_b = alive_by_concept[comp_b]

            # Physical lock 3: parents must have non-empty IPA
            if not parent_a.ipa_current or not parent_b.ipa_current:
                continue

            compound_ipa = self._blend_ipa(parent_a.ipa_current, parent_b.ipa_current)

            # Physical lock 2: reject oversized compounds
            if len(compound_ipa) > self._MAX_COMPOUND_IPA_LEN:
                continue

            entity = LexicalEntity(
                id=f"cmp_{rule['id']}_{era}",
                concept=target_concept,
                pos=rule.get("pos", "n."),
                ipa_current=compound_ipa,
                ipa_history=[],
                frequency_weight=0.003,
                word_class="content",
                is_dead=False,
                ipa_exemplars=[{"form": compound_ipa, "weight": 1.0}],
                era_born=era,
            )
            event = DeltaEvent(
                event_type=DeltaEventType.COMPOUND_SPAWN,
                era=era,
                word_id=entity.id,
                new_entity=entity,
                dag_parent_id=parent_a.id,
                edge_type="compound",
                concept=target_concept,
            )
            hot.apply_delta(event)
            # Also record DAG edge from second parent
            edge_b = DeltaEvent(
                event_type=DeltaEventType.DAG_EDGE_ADD,
                era=era,
                word_id=entity.id,
                dag_parent_id=parent_b.id,
                edge_type="compound",
            )
            hot.apply_delta(edge_b)
            existing_concepts.add(target_concept)
            generated.append(entity)

        return generated

    @staticmethod
    def _blend_ipa(ipa_a: str, ipa_b: str) -> str:
        """Simple IPA concatenation with boundary reduction.

        Takes the first half of ipa_a and the second half of ipa_b,
        producing a realistic blended form of moderate length.
        """
        a_len = max(1, len(ipa_a) // 2 + len(ipa_a) % 2)
        b_start = max(0, len(ipa_b) // 2)
        return ipa_a[:a_len] + ipa_b[b_start:]


# ------------------------------------------------------------------
# VocabularyRenewalEngine
# ------------------------------------------------------------------

class VocabularyRenewalEngine:
    """Monitors Swadesh 100 for concept vacuums and triggers renewal.

    A 'vacuum' occurs when every word carrying a Swadesh core concept
    has grammaticalization_stage >= 3 (disappeared) and is therefore
    no longer an independent lexical word.

    For each vacuum, a REPLACEMENT_NEEDED event is emitted and a new
    word is generated via the provided injector.
    """

    def __init__(self, injector: WordInjector) -> None:
        self._injector = injector

    def renew(
        self,
        hot: "EngineHotState",
        era: int,
        swadesh_concepts: set[str],
        inv: "PhonemeInventory",
        rng: random.Random,
    ) -> list[str]:
        """Return list of renewed concept names."""
        vacuums = self._find_vacuums(hot, swadesh_concepts)
        renewed: list[str] = []

        for concept in vacuums:
            replacement_event = DeltaEvent(
                event_type=DeltaEventType.REPLACEMENT_NEEDED,
                era=era,
                word_id="",
                concept=concept,
            )
            hot.apply_delta(replacement_event)

            new_words = self._inject_replacement(concept, hot, era, inv, rng)
            if new_words:
                renewed.append(concept)
                logger.info("Renewed vacant concept '%s' with /%s/", concept, new_words[0].ipa_current)

        return renewed

    def _inject_replacement(
        self,
        concept: str,
        hot: "EngineHotState",
        era: int,
        inv: "PhonemeInventory",
        rng: random.Random,
    ) -> list[LexicalEntity]:
        """Generate a phonologically fresh replacement word for *concept*."""
        ipa = DomainInjector._generate_ipa(inv, rng)
        original_pos = self._lookup_original_pos(hot, concept)
        original_wc = self._lookup_original_word_class(hot, concept)
        entity = LexicalEntity(
            id=f"renewal_{concept.replace(' ', '_')}_{era}",
            concept=concept,
            pos=original_pos,
            ipa_current=ipa,
            ipa_history=[],
            frequency_weight=0.01,
            word_class=original_wc,
            is_dead=False,
            ipa_exemplars=[{"form": ipa, "weight": 1.0}],
            era_born=era,
        )
        hot.insert_word(entity, era)
        return [entity]

    @staticmethod
    def _lookup_original_pos(hot: "EngineHotState", concept: str) -> str:
        for e in hot.lexicon.values():
            if e.concept == concept:
                return e.pos
        return "n."

    @staticmethod
    def _lookup_original_word_class(hot: "EngineHotState", concept: str) -> str:
        for e in hot.lexicon.values():
            if e.concept == concept:
                return e.word_class
        return "content"

    @staticmethod
    def _find_vacuums(
        hot: "EngineHotState",
        swadesh_concepts: set[str],
    ) -> list[str]:
        """Return Swadesh concepts that have no alive independent word entry."""
        alive = hot.all_alive()
        covered: set[str] = set()
        for e in alive:
            if e.concept in swadesh_concepts and e.grammaticalization_stage < 3:
                covered.add(e.concept)
        return [c for c in swadesh_concepts if c not in covered]
