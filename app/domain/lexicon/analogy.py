from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.lexicon.models import LexicalEntity
    from app.domain.phonology.phoneme import PhonemeInventory
    from app.domain.syntax.typology import TypologyMatrix


class AnalogyPropagator:
    """Spreads morphological patterns from a source word to phonologically similar words.

    When a word acquires a new affix (suffix or prefix) through grammaticalization,
    analogical pressure can cause the same pattern to spread to other words that
    share a similar phonological profile, measured by shared phonological features
    (using Phoneme.matches() per development.md rule 10 — no string comparisons).

    Similarity metric:
        Two words are phonologically similar if they share >= similarity_threshold
        of their phoneme feature vectors (Hamming overlap on feature set).
        Features compared: syllabic, voiced, nasal, continuant, high, back, round.

    Spread is probabilistic — each candidate independently draws against spread_rate.
    """

    _COMPARED_FEATURES: list[dict[str, bool]] = [
        {"syllabic": True},
        {"voiced": True},
        {"nasal": True},
        {"continuant": True},
        {"high": True},
        {"back": True},
        {"round": True},
    ]

    def __init__(
        self,
        inventory: "PhonemeInventory",
        spread_rate: float = 0.3,
        similarity_threshold: float = 0.6,
    ) -> None:
        self._inventory = inventory
        self.spread_rate = spread_rate
        self.similarity_threshold = similarity_threshold

    def propagate(
        self,
        source: "LexicalEntity",
        candidates: list["LexicalEntity"],
        morpheme_key: str,
        morpheme_ipa: str,
        typology: "TypologyMatrix",
        rng: random.Random,
    ) -> list[str]:
        """Return IDs of entities that should receive the morpheme pattern.

        The source entity is excluded from the candidate pool. Candidates
        are filtered by phonological similarity, then sampled by spread_rate.
        The caller is responsible for injecting ``morpheme_key → morpheme_ipa``
        into each affected entity's accessible TypologyMatrix.morpheme_table.
        """
        affected: list[str] = []
        source_profile = self._feature_profile(source.ipa_current)

        for candidate in candidates:
            if candidate.id == source.id or candidate.is_dead:
                continue
            if candidate.word_class != source.word_class:
                continue
            cand_profile = self._feature_profile(candidate.ipa_current)
            if self._similarity(source_profile, cand_profile) < self.similarity_threshold:
                continue
            if rng.random() < self.spread_rate:
                affected.append(candidate.id)

        return affected

    def _feature_profile(self, ipa: str) -> list[list[bool]]:
        """Return a list of feature-boolean vectors for each phoneme in the IPA string."""
        tokens = self._inventory.tokenize(ipa)
        profile: list[list[bool]] = []
        for token in tokens:
            phoneme = self._inventory.find_by_symbol(token)
            if phoneme is None:
                continue
            vec = [phoneme.matches(spec) for spec in self._COMPARED_FEATURES]
            profile.append(vec)
        return profile

    def _similarity(
        self,
        profile_a: list[list[bool]],
        profile_b: list[list[bool]],
    ) -> float:
        """Compute normalised feature overlap between two phoneme-sequence profiles.

        Compares position-by-position up to min(len(a), len(b)) phonemes;
        unmatched trailing phonemes count as mismatches for the longer word.
        """
        if not profile_a and not profile_b:
            return 1.0
        if not profile_a or not profile_b:
            return 0.0

        n_features = len(self._COMPARED_FEATURES)
        min_len = min(len(profile_a), len(profile_b))
        max_len = max(len(profile_a), len(profile_b))

        matches = 0
        for i in range(min_len):
            for f_a, f_b in zip(profile_a[i], profile_b[i]):
                if f_a == f_b:
                    matches += 1

        total = max_len * n_features
        return matches / total if total > 0 else 0.0
