from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class PortmanteauMorpheme:
    """A fused morpheme that encodes multiple grammatical features in one surface form.

    This implements the Feature Fusion concept from development.md §2.2:
    two adjacent agglutinative suffixes A+B, when frequently co-occurring
    and phonologically eroded, merge into a single opaque ending that
    encodes the full feature bundle of both A and B simultaneously.

    Example: Latin `-o` encodes {person:1st, number:sg, tense:pres, voice:active}
    instead of separate *-m + *-ba + ... endings.
    """

    surface_form: str
    feature_bundle: dict[str, str]
    source_keys: frozenset[str]


class PortmanteauRegistry:
    """Stores and retrieves PortmanteauMorpheme entries.

    Fusion trigger (development.md §2.2):
    When two morpheme keys A and B co-occur in the same planning step
    repeatedly (cooccurrence_threshold times), and their combined surface
    form either matches an existing morpheme (homophones) or has been
    phonologically eroded, register as a PortmanteauMorpheme and mark
    the original analytic forms as dead.

    Usage::
        registry = PortmanteauRegistry(cooccurrence_threshold=5)
        # Track co-occurrence during MorphologicalPlanner.plan()
        registry.track_cooccurrence("PAST", "1SG")
        # After planning, check for fusion
        fused = registry.maybe_fuse("PAST", "et", "1SG", "m", morpheme_table)
        if fused:
            morpheme_table["PAST+1SG"] = fused.surface_form
    """

    def __init__(self, cooccurrence_threshold: int = 5) -> None:
        self.cooccurrence_threshold = cooccurrence_threshold
        self._entries: dict[frozenset[str], PortmanteauMorpheme] = {}
        self._dead_keys: set[str] = set()
        self._cooccurrence: dict[frozenset[str], int] = defaultdict(int)

    def register(
        self,
        key_a: str,
        key_b: str,
        fused_ipa: str,
        feature_bundle: dict[str, str],
    ) -> PortmanteauMorpheme:
        """Manually register a PortmanteauMorpheme for a feature pair."""
        source = frozenset({key_a, key_b})
        morpheme = PortmanteauMorpheme(
            surface_form=fused_ipa,
            feature_bundle=feature_bundle,
            source_keys=source,
        )
        self._entries[source] = morpheme
        return morpheme

    def lookup(self, feature_set: frozenset[str]) -> PortmanteauMorpheme | None:
        """Return fused morpheme if the exact feature set has been registered."""
        return self._entries.get(feature_set)

    def track_cooccurrence(self, key_a: str, key_b: str) -> int:
        """Increment co-occurrence counter for a pair. Returns updated count."""
        pair = frozenset({key_a, key_b})
        self._cooccurrence[pair] += 1
        return self._cooccurrence[pair]

    def cooccurrence_count(self, key_a: str, key_b: str) -> int:
        return self._cooccurrence[frozenset({key_a, key_b})]

    def maybe_fuse(
        self,
        key_a: str,
        ipa_a: str,
        key_b: str,
        ipa_b: str,
        existing_morpheme_values: set[str],
    ) -> PortmanteauMorpheme | None:
        """Attempt to fuse two morphemes if conditions are met.

        Conditions (development.md §2.2):
        1. Co-occurrence count >= cooccurrence_threshold
        2. Combined IPA conflicts with an existing morpheme value (homophone trigger)
           OR the combined form can be phonologically simplified (when ipa_a ends with
           the same segment that ipa_b starts with → haplology fusion).

        On success, registers the new PortmanteauMorpheme and marks both
        source keys as dead in this registry.
        """
        pair = frozenset({key_a, key_b})
        if self._cooccurrence[pair] < self.cooccurrence_threshold:
            return None

        if pair in self._entries:
            return self._entries[pair]

        combined = ipa_a + ipa_b
        fused_ipa = self._compute_fused_form(ipa_a, ipa_b)

        if fused_ipa not in existing_morpheme_values and fused_ipa == combined:
            return None

        feature_bundle = {
            "key_a": key_a,
            "key_b": key_b,
        }
        morpheme = PortmanteauMorpheme(
            surface_form=fused_ipa,
            feature_bundle=feature_bundle,
            source_keys=pair,
        )
        self._entries[pair] = morpheme
        self._dead_keys.add(key_a)
        self._dead_keys.add(key_b)
        return morpheme

    def is_dead(self, key: str) -> bool:
        """True if the key has been absorbed into a portmanteau."""
        return key in self._dead_keys

    def _compute_fused_form(self, ipa_a: str, ipa_b: str) -> str:
        """Haplology: if A ends and B starts with the same segment, drop one copy."""
        if ipa_a and ipa_b and ipa_a[-1] == ipa_b[0]:
            return ipa_a + ipa_b[1:]
        return ipa_a + ipa_b
