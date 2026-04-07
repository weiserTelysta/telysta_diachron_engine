from __future__ import annotations

import random

from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory


LOCK_THRESHOLD = 0.06  # Above ErosionModel._FUNCTION_WORD_THRESHOLD=0.04 so the 1.0 base-rate range is reachable by operators


class IrregularScarManager:
    """High-frequency word lock + phonological scar mechanism.

    Locked words are excluded from normal rule-based sound change.
    Instead, with a low probability they acquire an irregular 'scar':
    a single random feature flip on one vowel or consonant, producing
    the historical irregularity seen in suppletive/high-frequency forms
    (go/went, be/was, etc.).

    Scar types applied (in order of cross-linguistic frequency):
      1. vowel_raising:  one vowel feature 'high' True → already high → skip
      2. vowel_lowering: one vowel feature 'high' False (if it is high)
      3. vowel_backing:  one vowel feature 'back' flip
      4. consonant_voicing_flip: flip 'voiced' on one consonant

    Only one scar is applied per word per call.
    """

    def __init__(self, lock_threshold: float = LOCK_THRESHOLD) -> None:
        self.lock_threshold = lock_threshold

    def is_locked(self, entity: LexicalEntity) -> bool:
        """Return True if the word's frequency qualifies it for irregularity lock."""
        return entity.frequency_weight > self.lock_threshold

    def try_scar(
        self,
        entity: LexicalEntity,
        rng: random.Random,
        inventory: PhonemeInventory,
        scar_prob: float = 0.05,
    ) -> tuple[str, str] | None:
        """Attempt to apply a phonological scar to a locked word.

        Returns (new_ipa, scar_key) if a scar was applied, else None.
        The caller is responsible for creating the DeltaEvent and appending
        scar_key to entity.scar_log.
        """
        if not self.is_locked(entity):
            return None
        if rng.random() >= scar_prob:
            return None

        tokens = inventory.tokenize(entity.ipa_current)
        result = self._apply_scar(tokens, rng, inventory, entity.scar_log)
        if result is None:
            return None
        new_tokens, scar_key = result
        if new_tokens == tokens:
            return None
        return "".join(new_tokens), scar_key

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_scar(
        self,
        tokens: list[str],
        rng: random.Random,
        inventory: PhonemeInventory,
        scar_log: list[str],
    ) -> tuple[list[str], str] | None:
        """Apply one random scar to a token sequence.

        Returns (modified_tokens, scar_key) or None if no scar could be applied.
        """
        phonemes = [inventory.find_by_symbol(t) for t in tokens]
        candidates = [(i, p) for i, p in enumerate(phonemes) if p is not None]
        if not candidates:
            return None

        rng.shuffle(candidates)

        for idx, phoneme in candidates:
            new_ipa = self._try_vowel_mutation(phoneme, inventory)
            if new_ipa is not None:
                result = list(tokens)
                result[idx] = new_ipa
                scar_key = f"vowel_mut:{phoneme.symbol}:{new_ipa}"
                return result, scar_key

            new_ipa = self._try_consonant_voicing_flip(phoneme, inventory, scar_log)
            if new_ipa is not None:
                result = list(tokens)
                result[idx] = new_ipa
                scar_key = f"cv_flip:{phoneme.symbol}:{new_ipa}"
                return result, scar_key
        return None

    @staticmethod
    def _try_vowel_mutation(
        phoneme, inventory: PhonemeInventory
    ) -> str | None:
        if not phoneme.features.get("syllabic"):
            return None
        # Attempt vowel raising (low→mid) then backing flip
        for feature, flip_to in [("low", False), ("back", not phoneme.features.get("back", False))]:
            if phoneme.features.get(feature) == (not flip_to):
                new_features = {**phoneme.features, feature: flip_to}
                candidate = inventory.find_by_features(new_features)
                if candidate and candidate.symbol != phoneme.symbol:
                    return candidate.symbol
        return None

    @staticmethod
    def _try_consonant_voicing_flip(
        phoneme, inventory: PhonemeInventory, scar_log: list[str]
    ) -> str | None:
        if phoneme.features.get("syllabic"):
            return None
        current_voiced = phoneme.features.get("voiced", False)
        new_features = {**phoneme.features, "voiced": not current_voiced}
        candidate = inventory.find_by_features(new_features)
        if candidate is None or candidate.symbol == phoneme.symbol:
            return None
        # Block oscillation: if the reverse of this flip was already applied, skip
        reverse_key = f"cv_flip:{candidate.symbol}:{phoneme.symbol}"
        if reverse_key in scar_log:
            return None
        return candidate.symbol
