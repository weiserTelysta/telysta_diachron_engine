from __future__ import annotations

from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory


FOSSIL_FREQ_THRESHOLD = 0.001  # below this, dead words are too rare to leave fossil traces
FOSSIL_MIN_SYLLABLES  = 2      # at least 2 syllables needed to extract a prefix


class FossilPrefixExtractor:
    """Extract the initial syllable of a dead word as a new fossil prefix entity.

    When a word dies (is_dead=True), if it was common enough and long enough,
    its opening CV/CVC syllable survives as a compounding prefix — modelling
    the historical residue seen in e.g. English 'fortnight' (fourteen + night).

    The extracted entity has:
      morpheme_type    = "prefix"
      dag_parent_ids   = [dead_entity.id]
      era_born         = current_era
      frequency_weight = dead_entity.frequency_weight * 0.3
    """

    def should_extract(
        self, entity: LexicalEntity, inventory: PhonemeInventory
    ) -> bool:
        if not entity.is_dead:
            return False
        if entity.frequency_weight < FOSSIL_FREQ_THRESHOLD:
            return False
        syllable_count = self._count_syllables(entity.ipa_current, inventory)
        return syllable_count >= FOSSIL_MIN_SYLLABLES

    def extract(
        self,
        entity: LexicalEntity,
        inventory: PhonemeInventory,
        current_era: int,
        id_suffix: str = "_fossil",
    ) -> LexicalEntity | None:
        """Return a new prefix LexicalEntity or None if extraction criteria not met."""
        if not self.should_extract(entity, inventory):
            return None

        first_syllable = self._extract_first_syllable(entity.ipa_current, inventory)
        if not first_syllable:
            return None

        return LexicalEntity(
            id=entity.id + id_suffix,
            concept=f"[fossil:{entity.concept}]",
            pos=entity.pos,
            ipa_current=first_syllable,
            ipa_history=[],
            frequency_weight=entity.frequency_weight * 0.3,
            word_class="function",
            is_dead=False,
            stress_pattern="",
            era_born=current_era,
            source_language=entity.source_language,
            morpheme_type="prefix",
            dag_parent_ids=[entity.id],
        )

    # ------------------------------------------------------------------
    # Internal syllable helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count_syllables(ipa: str, inventory: PhonemeInventory) -> int:
        """Count syllable nuclei (vowels) as a syllable count proxy."""
        tokens = inventory.tokenize(ipa)
        return sum(
            1 for t in tokens
            if (p := inventory.find_by_symbol(t)) and p.features.get("syllabic")
        )

    def _extract_first_syllable(
        self, ipa: str, inventory: PhonemeInventory
    ) -> str | None:
        """Return the first CV(C) syllable from the IPA string.

        Algorithm: collect all consonants up to and including the first vowel,
        then optionally append one immediately following consonant if the
        next token is also a consonant (CVC capture).
        """
        tokens = inventory.tokenize(ipa)
        result: list[str] = []
        vowel_seen = False

        for i, tok in enumerate(tokens):
            phoneme = inventory.find_by_symbol(tok)
            if phoneme is None:
                if vowel_seen:
                    break
                result.append(tok)
                continue

            is_vowel = phoneme.features.get("syllabic", False)

            if not vowel_seen:
                result.append(tok)
                if is_vowel:
                    vowel_seen = True
            else:
                if not is_vowel:
                    # Look ahead: if next token is also a consonant or end, append
                    next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
                    next_p = inventory.find_by_symbol(next_tok) if next_tok else None
                    if next_p is None or not next_p.features.get("syllabic"):
                        result.append(tok)
                break

        if not vowel_seen or not result:
            return None
        return "".join(result)
