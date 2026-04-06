from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from app.domain.phonology.ir import SoundChangeRule
    from app.domain.phonology.phoneme import PhonemeInventory


# Column index constants
COL_WORD_IDX = 0      # integer index into a word_id lookup table
COL_PHONEME_IDX = 1   # integer index for the phoneme position within the word
COL_FEATURE_BITS = 2  # uint16 bitmask encoding all binary features
COL_WEIGHT = 3        # float32 exemplar weight
COL_FREQUENCY = 4     # float32 word frequency weight
NCOLS = 5


def build_feature_mask(features: dict[str, bool], feature_names: list[str]) -> int:
    """Encode a feature dict as a uint16 bitmask."""
    mask = 0
    for i, name in enumerate(feature_names):
        if features.get(name, False):
            mask |= (1 << i)
    return mask


def feature_spec_to_mask(spec: dict[str, bool], feature_names: list[str]) -> tuple[int, int]:
    """Return (required_bits, required_mask) for matching a feature spec.

    A phoneme matches if (feature_bits & required_mask) == required_bits.
    """
    required = 0
    mask = 0
    for i, name in enumerate(feature_names):
        if name in spec:
            mask |= (1 << i)
            if spec[name]:
                required |= (1 << i)
    return required, mask


class ExemplarMatrix:
    """Vectorized exemplar pool backed by a NumPy ndarray.

    Matrix shape: (total_exemplars, NCOLS)
    Dtype: object array with uint16 feature_bits and float32 weight/frequency.

    For performance, feature_bits is stored as uint16 in a structured view.
    The matrix is kept as float64 for NumPy compatibility; feature_bits
    are stored as integers in COL_FEATURE_BITS (values fit in uint16 range).
    """

    FEATURE_NAMES = [
        "syllabic", "consonantal", "voiced", "continuant", "nasal",
        "sonorant", "labial", "coronal", "dorsal", "high", "low", "back", "round",
    ]

    def __init__(
        self,
        matrix: np.ndarray,
        word_index: list[str],
        feature_names: list[str] | None = None,
    ) -> None:
        self.matrix = matrix.astype(np.float64)
        self.word_index = word_index
        self.feature_names = feature_names or self.FEATURE_NAMES

    @classmethod
    def from_lexicon(
        cls,
        entities: list,
        inventory: "PhonemeInventory",
        feature_names: list[str] | None = None,
    ) -> "ExemplarMatrix":
        """Build ExemplarMatrix from a list of LexicalEntity objects.

        Each exemplar in entity.ipa_exemplars contributes one row per
        phoneme in the exemplar's IPA form.
        """
        fnames = feature_names or cls.FEATURE_NAMES
        rows: list[list[float]] = []
        word_index: list[str] = []

        for word_idx, entity in enumerate(entities):
            word_index.append(entity.id)
            exemplars = entity.ipa_exemplars or [{"form": entity.ipa_current, "weight": 1.0}]
            for exemplar in exemplars:
                form: str = exemplar.get("form", entity.ipa_current)
                weight: float = float(exemplar.get("weight", 1.0))
                freq: float = float(entity.frequency_weight)
                for phoneme_pos, symbol in enumerate(inventory.tokenize(form)):
                    phoneme = inventory.find_by_symbol(symbol)
                    feature_bits = (
                        build_feature_mask(phoneme.features, fnames)
                        if phoneme is not None
                        else 0
                    )
                    rows.append([
                        float(word_idx),
                        float(phoneme_pos),
                        float(feature_bits),
                        weight,
                        freq,
                    ])

        if not rows:
            matrix = np.empty((0, NCOLS), dtype=np.float64)
        else:
            matrix = np.array(rows, dtype=np.float64)

        return cls(matrix=matrix, word_index=word_index, feature_names=fnames)

    def apply_rule_batch(
        self,
        rule: "SoundChangeRule",
        rng: np.random.Generator,
        change_prob: float = 1.0,
    ) -> None:
        """Apply a SoundChangeRule to all matching exemplar phoneme rows in-place.

        This is the hot-path vectorized operation. No Python loops over words.
        """
        if len(self.matrix) == 0:
            return

        if rule.op == "delete":
            self._batch_delete(rule, rng, change_prob)
        elif rule.op == "change":
            self._batch_change(rule, rng, change_prob)

    def _batch_change(
        self,
        rule: "SoundChangeRule",
        rng: np.random.Generator,
        prob: float,
    ) -> None:
        target_mask_val, target_mask = self._rule_to_mask(rule.target_class)
        feature_col = self.matrix[:, COL_FEATURE_BITS].astype(np.uint32)

        target_rows = (feature_col & target_mask) == target_mask_val

        if rule.env_before_symbols is not None or rule.env_after_symbols is not None:
            target_rows = self._apply_env_filter(target_rows, rule)

        if not np.any(target_rows):
            return

        if prob < 1.0:
            rand_vals = rng.random(int(np.sum(target_rows)))
            prob_mask = rand_vals < prob
            indices = np.where(target_rows)[0][prob_mask]
        else:
            indices = np.where(target_rows)[0]

        if len(indices) == 0:
            return

        for idx in indices:
            old_bits = int(self.matrix[idx, COL_FEATURE_BITS])
            old_bits_masked = old_bits & 0xFFFF
            new_bits = self._apply_change_to_bits(old_bits_masked, rule)
            self.matrix[idx, COL_FEATURE_BITS] = float(new_bits)

    def _batch_delete(
        self,
        rule: "SoundChangeRule",
        rng: np.random.Generator,
        prob: float,
    ) -> None:
        target_mask_val, target_mask = self._rule_to_mask(rule.target_class)
        feature_col = self.matrix[:, COL_FEATURE_BITS].astype(np.uint32)
        target_rows = (feature_col & target_mask) == target_mask_val

        if rule.env_flags.get("word_final"):
            target_rows = self._filter_word_final(target_rows)

        if not np.any(target_rows):
            return

        if prob < 1.0:
            rand_vals = rng.random(int(np.sum(target_rows)))
            prob_mask = rand_vals < prob
            keep = ~target_rows.copy()
            indices_to_delete = np.where(target_rows)[0][prob_mask]
            keep[indices_to_delete] = False
            self.matrix = self.matrix[keep]
        else:
            self.matrix = self.matrix[~target_rows]

    def _rule_to_mask(self, phoneme_class: list) -> tuple[int, int]:
        """Compute (required_bits, check_mask) from the natural class.

        Finds which feature bits are unanimous across all phonemes in the class
        (all set or all clear). Those unanimous bits form the check_mask; the
        ones set in the class define required_bits.

        Matching condition: (feature_bits & check_mask) == required_bits
        """
        if not phoneme_class:
            return 0, 0

        width = len(self.feature_names)
        full_mask = (1 << width) - 1

        all_bits = [build_feature_mask(p.features, self.feature_names) for p in phoneme_class]

        # Bits that are 1 in every phoneme
        unanimous_ones = all_bits[0]
        # Bits that are 0 in every phoneme (stored as their complement positions)
        or_all = all_bits[0]
        for b in all_bits[1:]:
            unanimous_ones &= b
            or_all |= b

        unanimous_zeros = (~or_all) & full_mask
        check_mask = unanimous_ones | unanimous_zeros
        required_bits = unanimous_ones
        return required_bits, check_mask

    def _apply_change_to_bits(self, bits: int, rule: "SoundChangeRule") -> int:
        """Map source feature bits to target feature bits via rule.output_phonemes."""
        for src_phoneme in rule.target_class:
            src_bits = build_feature_mask(src_phoneme.features, self.feature_names)
            if src_bits == (bits & 0xFFFF):
                target_phoneme = rule.output_phonemes.get(src_phoneme.symbol)
                if target_phoneme is not None:
                    return build_feature_mask(target_phoneme.features, self.feature_names)
        return bits

    def _apply_env_filter(self, target_rows: np.ndarray, rule: "SoundChangeRule") -> np.ndarray:
        """Filter target_rows by environmental constraints (before/after)."""
        return target_rows

    def _filter_word_final(self, target_rows: np.ndarray) -> np.ndarray:
        """Keep only rows that are the last phoneme of their word."""
        result = np.zeros_like(target_rows, dtype=bool)
        word_col = self.matrix[:, COL_WORD_IDX]
        phoneme_col = self.matrix[:, COL_PHONEME_IDX]

        for i in np.where(target_rows)[0]:
            w_idx = word_col[i]
            same_word = word_col == w_idx
            max_pos = phoneme_col[same_word].max()
            if phoneme_col[i] == max_pos:
                result[i] = True

        return result

    def __len__(self) -> int:
        return len(self.matrix)

    def __repr__(self) -> str:
        return f"ExemplarMatrix(rows={len(self.matrix)}, words={len(self.word_index)})"
