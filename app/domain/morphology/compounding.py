from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.phonology.validator import WellFormednessValidator


@dataclass
class CompoundingConfig:
    era_threshold: int = 5
    max_new_per_era: int = 5
    # Only content words are eligible parents
    eligible_word_classes: list[str] = field(default_factory=lambda: ["content"])
    # Minimum frequency_weight for a word to be sampled as a parent
    min_frequency_weight: float = 0.0
    # Probability that any two randomly chosen content words will be compounded
    compound_probability: float = 0.3


class CompoundingEngine:
    """Morphological compounding: combines two content word roots into a new lexical entry.

    Produces CVCCVC+ structures naturally by concatenating existing roots, then
    runs WellFormednessValidator to repair any illegal consonant clusters via epenthesis.

    Architecture note: this is a LexiconLevel operation, NOT an EvolutionOperator.
    It must be invoked by the era-advancement pipeline separately from the
    phonological operator registry, after phonological operators have run.
    """

    def __init__(
        self,
        inventory: PhonemeInventory,
        validator: WellFormednessValidator,
        config: CompoundingConfig | None = None,
    ) -> None:
        self.inventory = inventory
        self.validator = validator
        self.config = config or CompoundingConfig()

    def generate_compounds(
        self,
        lexicon: list[LexicalEntity],
        era: int,
        rng: random.Random,
    ) -> list[LexicalEntity]:
        """Generate new compound LexicalEntities from the current lexicon.

        Returns only new entries; the caller is responsible for appending them to
        the active lexicon (EngineHotState).

        Eligibility:
          - era >= era_threshold
          - source word: not dead, word_class in eligible_word_classes
          - source word: frequency_weight >= min_frequency_weight
        """
        if era < self.config.era_threshold:
            return []

        candidates = [
            e for e in lexicon
            if not e.is_dead
            and e.word_class in self.config.eligible_word_classes
            and e.frequency_weight >= self.config.min_frequency_weight
            and e.ipa_current
        ]

        if len(candidates) < 2:
            return []

        weights = [e.frequency_weight for e in candidates]
        new_entries: list[LexicalEntity] = []
        attempts = 0
        max_attempts = self.config.max_new_per_era * 4

        while len(new_entries) < self.config.max_new_per_era and attempts < max_attempts:
            attempts += 1
            if rng.random() > self.config.compound_probability:
                continue

            parent1, parent2 = rng.choices(candidates, weights=weights, k=2)
            if parent1.id == parent2.id:
                continue

            compound = self._build_compound(parent1, parent2, era)
            if compound is not None:
                new_entries.append(compound)

        return new_entries

    def _build_compound(
        self,
        parent1: LexicalEntity,
        parent2: LexicalEntity,
        era: int,
    ) -> LexicalEntity | None:
        """Concatenate two IPA forms and repair the result via the validator."""
        seq1 = self.inventory.tokenize(parent1.ipa_current)
        seq2 = self.inventory.tokenize(parent2.ipa_current)

        if not seq1 or not seq2:
            return None

        combined = seq1 + seq2
        result = self.validator.validate(combined)
        repaired_seq = result.sequence

        ipa_compound = "".join(repaired_seq)
        concept = f"{parent1.concept}_{parent2.concept}"

        # Frequency weight: geometric mean of parents, discounted as a new word
        compound_weight = (parent1.frequency_weight * parent2.frequency_weight) ** 0.5 * 0.5

        compound_id = f"compound_{parent1.id}_{parent2.id}_era{era}"

        return LexicalEntity(
            id=compound_id,
            concept=concept,
            pos=parent1.pos,
            ipa_current=ipa_compound,
            ipa_history=[],
            frequency_weight=compound_weight,
            word_class="content",
            is_dead=False,
            ipa_exemplars=[{"form": ipa_compound, "weight": 1.0}],
            stress_pattern="penultimate",
            era_born=era,
            morpheme_type="compound",
            dag_parent_ids=[parent1.id, parent2.id],
        )
