from __future__ import annotations


# Frequency thresholds (Zipf-Mandelbrot calibrated against swadesh_207.json)
_FUNCTION_WORD_THRESHOLD = 0.04   # function-word core: changes every era
_HIGH_FREQ_THRESHOLD     = 0.01   # high-frequency content words
_MID_FREQ_THRESHOLD      = 0.001  # mid-frequency words

# Stress patterns that indicate a word-root's nucleus is in a prominent position
_PROMINENT_PATTERNS = {"initial", "penultimate"}


class ErosionModel:
    """Dual-variable erosion rate: f(frequency_weight, stress_pattern).

    Replaces the single-variable _freq_to_rate function from Phase 0/1.

    Linguistic basis (development.md §2.5.2):
      - High-frequency words in unstressed/final position → rapid erosion
      - High-frequency words with initial/penultimate stress → erosion resistance
        (may undergo fortition instead of lenition)
      - Low-frequency words erode slowly regardless of stress
    """

    def rate(self, freq_weight: float, stress_pattern: str = "") -> float:
        """Return the per-era change probability for a word.

        Args:
            freq_weight:    LexicalEntity.frequency_weight
            stress_pattern: LexicalEntity.stress_pattern
                            ("initial" | "penultimate" | "final" | "")

        Returns:
            Float in [0.0, 1.0] — probability that a sound change is applied
            to this word in the current era (before operator-specific rate
            multiplication).
        """
        base = self._base_rate(freq_weight)
        multiplier = self._stress_multiplier(freq_weight, stress_pattern)
        return min(base * multiplier, 1.0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _base_rate(freq_weight: float) -> float:
        if freq_weight > _FUNCTION_WORD_THRESHOLD:
            return 1.00   # function-word core: guaranteed change
        if freq_weight > _HIGH_FREQ_THRESHOLD:
            return 0.75   # high-frequency content words
        if freq_weight > _MID_FREQ_THRESHOLD:
            return 0.45   # mid-frequency words
        return 0.20        # rare words

    @staticmethod
    def _stress_multiplier(freq_weight: float, stress_pattern: str) -> float:
        """Stress modifies erosion only for high-frequency words.

        - Prominent stress (initial/penultimate) on high-freq root → 0.5× (resistance)
        - Unstressed or final syllable high-freq item    → 1.5× (rapid erosion)
        - Mid/low freq words: stress has no mechanical effect at this scale
        """
        if freq_weight <= _MID_FREQ_THRESHOLD:
            return 1.0

        if stress_pattern in _PROMINENT_PATTERNS:
            return 0.5    # stressed root resists erosion
        if stress_pattern in ("final", ""):
            return 1.5    # unstressed/final → rapid erosion (clitics, suffixes)
        return 1.0
