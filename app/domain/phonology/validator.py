from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.domain.phonology.phoneme import PhonemeInventory

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    is_valid: bool
    sequence: list[str]
    message: str = ""


class WellFormednessValidator:
    """Checks phonological well-formedness of an IPA symbol sequence.

    Validation flow per the spec:
      execute rule → validate → legal → continue
                              → illegal → epenthesis repair → re-validate
                                        → still illegal → rollback + log

    Two-tier legality check:
      Tier 1 (max consecutive consonants): catches gross clusters regardless of position.
      Tier 2 (onset/coda constraints): validates syllable-position-specific clusters.
    """

    def __init__(
        self,
        inventory: PhonemeInventory,
        onset_clusters: set[str] | None = None,
        coda_set: set[str] | None = None,
        illegal_coda_finals: set[str] | None = None,
        max_onset_consonants: int = 2,
        max_coda_consonants: int = 1,
        epenthetic_vowel: str = "ɪ",
    ) -> None:
        self.inventory = inventory
        self.onset_clusters: set[str] = onset_clusters or set()
        self.coda_set: set[str] = coda_set or set()
        self.illegal_coda_finals: set[str] = illegal_coda_finals or set()
        self.max_onset_consonants = max_onset_consonants
        self.max_coda_consonants = max_coda_consonants

        available_symbols = {p.symbol for p in inventory.phonemes}
        if epenthetic_vowel in available_symbols:
            self.epenthetic_vowel = epenthetic_vowel
        else:
            vowel_symbols = [p.symbol for p in inventory.vowels]
            self.epenthetic_vowel = vowel_symbols[0] if vowel_symbols else "a"

        self._vowel_symbols: frozenset[str] = frozenset(
            p.symbol for p in inventory.vowels
        )
        self._consonant_symbols: frozenset[str] = frozenset(
            p.symbol for p in inventory.consonants
        )

    @classmethod
    def from_config(
        cls,
        inventory: PhonemeInventory,
        config_path: str | Path,
    ) -> "WellFormednessValidator":
        """Load constraints from a phonotactics JSON config file."""
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)

        fallback = cfg.get("epenthetic_vowel_fallback", "a")
        raw_ep = cfg.get("epenthetic_vowel", fallback)
        available = {p.symbol for p in inventory.phonemes}
        epenthetic = raw_ep if raw_ep in available else fallback

        return cls(
            inventory=inventory,
            onset_clusters=set(cfg.get("allowed_onset_clusters", [])),
            coda_set=set(cfg.get("allowed_codas", [])),
            illegal_coda_finals=set(cfg.get("illegal_coda_finals", [])),
            max_onset_consonants=cfg.get("max_onset_consonants", 2),
            max_coda_consonants=cfg.get("max_coda_consonants", 1),
            epenthetic_vowel=epenthetic,
        )

    def validate(self, sequence: list[str]) -> ValidationResult:
        """Return a ValidationResult. If invalid, attempt epenthesis repair."""
        if self._is_legal(sequence):
            return ValidationResult(is_valid=True, sequence=sequence)

        repaired = self._repair_epenthesis(sequence)
        if self._is_legal(repaired):
            return ValidationResult(is_valid=True, sequence=repaired, message="epenthesis applied")

        return ValidationResult(
            is_valid=False,
            sequence=sequence,
            message=f"illegal sequence cannot be repaired: {sequence}",
        )

    def is_legal(self, sequence: list[str]) -> bool:
        """Return whether *sequence* is legal without applying repair."""
        return self._is_legal(sequence)

    def validate_or_rollback(
        self,
        sequence: list[str],
        original: list[str],
        rule_name: str = "",
    ) -> list[str]:
        """Apply validation; return repaired sequence on success, original on failure."""
        result = self.validate(sequence)
        if result.is_valid:
            return result.sequence
        logger.warning(
            "Rule '%s' produced illegal sequence %s — rolling back to %s",
            rule_name,
            sequence,
            original,
        )
        return original

    def would_create_illegal_coda(self, sequence: list[str]) -> bool:
        """True if the sequence ends in a symbol listed in illegal_coda_finals."""
        if not sequence or not self.illegal_coda_finals:
            return False
        return sequence[-1] in self.illegal_coda_finals

    def _is_legal(self, sequence: list[str]) -> bool:
        if not sequence:
            return True

        syllables = self._syllabify(sequence)
        for onset, _, coda in syllables:
            if not self._onset_legal(onset):
                return False
            if not self._coda_legal(coda):
                return False
        return True

    def _syllabify(self, sequence: list[str]) -> list[tuple[list[str], str, list[str]]]:
        """Naive syllabification: each vowel is a nucleus.

        Returns list of (onset_consonants, nucleus_symbol, coda_consonants).
        Pre-initial consonants and post-final consonants are attributed to the
        nearest syllable boundary.
        """
        nuclei_positions: list[int] = [
            i for i, s in enumerate(sequence) if s in self._vowel_symbols
        ]

        if not nuclei_positions:
            # All consonants — treat as a single empty-nucleus syllable
            return [(list(sequence), "", [])]

        syllables: list[tuple[list[str], str, list[str]]] = []

        for syl_idx, nuc_pos in enumerate(nuclei_positions):
            prev_nuc = nuclei_positions[syl_idx - 1] if syl_idx > 0 else -1
            next_nuc = nuclei_positions[syl_idx + 1] if syl_idx + 1 < len(nuclei_positions) else len(sequence)

            onset_start = prev_nuc + 1
            onset_end = nuc_pos
            onset = [sequence[i] for i in range(onset_start, onset_end)
                     if sequence[i] in self._consonant_symbols]

            coda_start = nuc_pos + 1
            coda_end = next_nuc
            # Coda = consonants after the nucleus up to the next nucleus's onset
            # Simple maximal-onset principle: assign consonants to next onset first
            inter = [sequence[i] for i in range(coda_start, coda_end)
                     if sequence[i] in self._consonant_symbols]
            if syl_idx + 1 < len(nuclei_positions):
                # keep only what can't form a legal onset for the next syllable
                coda = self._split_coda_onset(inter)[0]
            else:
                coda = inter  # word-final: everything is coda

            syllables.append((onset, sequence[nuc_pos], coda))

        return syllables

    def _split_coda_onset(self, inter: list[str]) -> tuple[list[str], list[str]]:
        """Maximal onset principle: assign as many consonants as possible to the onset."""
        if not inter:
            return [], []
        # Try to find the longest suffix of inter that forms a legal onset
        for split in range(len(inter) + 1):
            prospective_onset = inter[split:]
            if self._onset_legal(prospective_onset):
                return inter[:split], prospective_onset
        # Nothing works: all consonants go to coda
        return inter, []

    def _onset_legal(self, onset: list[str]) -> bool:
        if not onset:
            return True
        if len(onset) > self.max_onset_consonants:
            return False
        if len(onset) == 1:
            return True
        cluster = "".join(onset)
        return cluster in self.onset_clusters

    def _coda_legal(self, coda: list[str]) -> bool:
        if not coda:
            return True
        if len(coda) > self.max_coda_consonants:
            cluster = "".join(coda)
            return cluster in self.coda_set
        cluster = "".join(coda)
        return cluster in self.coda_set or len(coda) == 1

    def _repair_epenthesis(self, sequence: list[str]) -> list[str]:
        """Insert epenthetic vowel to break illegal consonant clusters.

        Inserts at the exact position where a cluster becomes illegal:
        - Onset: after max_onset_consonants consonants before a vowel
        - Coda: after max_coda_consonants consonants at word end
        """
        result: list[str] = []
        i = 0
        while i < len(sequence):
            sym = sequence[i]
            if sym in self._consonant_symbols:
                # Gather the full consonant run
                run_start = i
                while i < len(sequence) and sequence[i] in self._consonant_symbols:
                    i += 1
                run = sequence[run_start:i]
                at_word_end = (i >= len(sequence))

                if at_word_end:
                    # Split into allowed coda chunks
                    result.extend(self._break_coda_run(run))
                else:
                    # This is an onset run: split if exceeds max
                    result.extend(self._break_onset_run(run))
            else:
                result.append(sym)
                i += 1
        return result

    def _break_onset_run(self, run: list[str]) -> list[str]:
        """Break a consonant run that serves as an onset, inserting epenthetic vowels."""
        out: list[str] = []
        pos = 0
        while pos < len(run):
            chunk_end = min(pos + self.max_onset_consonants, len(run))
            chunk = run[pos:chunk_end]
            out.extend(chunk)
            pos = chunk_end
            if pos < len(run):
                out.append(self.epenthetic_vowel)
        return out

    def _break_coda_run(self, run: list[str]) -> list[str]:
        """Break a word-final consonant run into legal coda chunks."""
        out: list[str] = []
        pos = 0
        while pos < len(run):
            chunk_end = min(pos + self.max_coda_consonants, len(run))
            chunk = run[pos:chunk_end]
            out.extend(chunk)
            pos = chunk_end
            if pos < len(run):
                out.append(self.epenthetic_vowel)
        return out
