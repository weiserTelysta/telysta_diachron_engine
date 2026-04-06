from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Phoneme:
    symbol: str
    features: dict[str, bool]
    xsampa: str = ""
    selection_weight: float = 1.0

    def __hash__(self) -> int:
        return hash((self.symbol, tuple(sorted(self.features.items()))))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Phoneme):
            return False
        return self.symbol == other.symbol and self.features == other.features

    def matches(self, feature_spec: dict[str, bool]) -> bool:
        """True if this phoneme belongs to the natural class described by feature_spec."""
        return all(self.features.get(f) == v for f, v in feature_spec.items())

    def apply_change(
        self,
        change_spec: dict[str, bool],
        inventory: "PhonemeInventory",
    ) -> "Phoneme | None":
        """Return the phoneme in inventory whose features match self + change_spec."""
        new_features = {**self.features, **change_spec}
        return inventory.find_by_features(new_features)


class PhonemeInventory:
    def __init__(self, phonemes: list[Phoneme]) -> None:
        self._phonemes: list[Phoneme] = phonemes
        # Sorted by symbol length descending for greedy tokenization
        self._sorted_symbols: list[str] = sorted(
            (p.symbol for p in phonemes), key=len, reverse=True
        )

    @property
    def phonemes(self) -> list[Phoneme]:
        return list(self._phonemes)

    @property
    def vowels(self) -> list[Phoneme]:
        return [p for p in self._phonemes if p.features.get("syllabic")]

    @property
    def consonants(self) -> list[Phoneme]:
        return [p for p in self._phonemes if not p.features.get("syllabic")]

    def get_natural_class(self, feature_spec: dict[str, bool]) -> list[Phoneme]:
        """Return all phonemes matching the feature bundle (natural class)."""
        return [p for p in self._phonemes if p.matches(feature_spec)]

    def find_by_features(self, features: dict[str, bool]) -> "Phoneme | None":
        """Find the unique phoneme whose feature dict exactly equals features."""
        candidates = [p for p in self._phonemes if p.features == features]
        return candidates[0] if candidates else None

    def find_by_symbol(self, symbol: str) -> "Phoneme | None":
        return next((p for p in self._phonemes if p.symbol == symbol), None)

    def find_by_xsampa(self, xsampa: str) -> "Phoneme | None":
        """Find phoneme by its X-SAMPA code."""
        return next((p for p in self._phonemes if p.xsampa == xsampa), None)

    def tokenize(self, ipa_string: str) -> list[str]:
        """Greedy longest-match tokenization of an IPA string into phoneme symbol tokens.

        Symbols sorted by length descending ensure multi-char symbols (e.g. 'tʃ')
        are matched before their single-char components ('t', 'ʃ').
        Unrecognized characters are returned as single-char tokens.
        """
        tokens: list[str] = []
        i = 0
        while i < len(ipa_string):
            matched = False
            for sym in self._sorted_symbols:
                if ipa_string[i:i + len(sym)] == sym:
                    tokens.append(sym)
                    i += len(sym)
                    matched = True
                    break
            if not matched:
                tokens.append(ipa_string[i])
                i += 1
        return tokens

    def parse_xsampa_string(self, xsampa_string: str) -> list[str]:
        """Convert an X-SAMPA string to a list of IPA symbols.

        Uses greedy longest-match over known X-SAMPA codes (sorted by length).
        Tokens without a matching X-SAMPA code are returned as-is.
        """
        xsampa_map: dict[str, str] = {
            p.xsampa: p.symbol for p in self._phonemes if p.xsampa
        }
        sorted_codes = sorted(xsampa_map.keys(), key=len, reverse=True)

        ipa_tokens: list[str] = []
        i = 0
        while i < len(xsampa_string):
            matched = False
            for code in sorted_codes:
                if xsampa_string[i:i + len(code)] == code:
                    ipa_tokens.append(xsampa_map[code])
                    i += len(code)
                    matched = True
                    break
            if not matched:
                ipa_tokens.append(xsampa_string[i])
                i += 1
        return ipa_tokens

    def sample_consonant(self, rng: random.Random) -> Phoneme:
        """Weighted random sample of one consonant by selection_weight."""
        pool = self.consonants
        weights = [p.selection_weight for p in pool]
        return rng.choices(pool, weights=weights, k=1)[0]

    def sample_vowel(self, rng: random.Random) -> Phoneme:
        """Weighted random sample of one vowel by selection_weight."""
        pool = self.vowels
        weights = [p.selection_weight for p in pool]
        return rng.choices(pool, weights=weights, k=1)[0]

    @classmethod
    def from_preset(cls, preset_name: str) -> "PhonemeInventory":
        """Load a PhonemeInventory from data/phoneme_presets/<preset_name>.json."""
        base = Path(__file__).resolve().parent.parent.parent.parent
        preset_path = base / "data" / "phoneme_presets" / f"{preset_name}.json"
        with open(preset_path, encoding="utf-8") as f:
            data = json.load(f)
        phonemes = [
            Phoneme(
                symbol=entry["symbol"],
                features=entry["features"],
                xsampa=entry.get("xsampa", ""),
                selection_weight=float(entry.get("selection_weight", 1.0)),
            )
            for entry in data["phonemes"]
        ]
        return cls(phonemes)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "PhonemeInventory":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        phonemes = [
            Phoneme(
                symbol=entry["symbol"],
                features=entry["features"],
                xsampa=entry.get("xsampa", ""),
                selection_weight=float(entry.get("selection_weight", 1.0)),
            )
            for entry in data["phonemes"]
        ]
        return cls(phonemes)

    def __len__(self) -> int:
        return len(self._phonemes)

    def __repr__(self) -> str:
        symbols = [p.symbol for p in self._phonemes]
        return f"PhonemeInventory({symbols})"
