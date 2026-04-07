import pytest

from app.domain.morphology.portmanteau import PortmanteauMorpheme, PortmanteauRegistry


class TestPortmanteauMorpheme:
    def test_fields_stored(self):
        m = PortmanteauMorpheme(
            surface_form="etm",
            feature_bundle={"tense": "past", "person": "1st"},
            source_keys=frozenset({"PAST", "1SG"}),
        )
        assert m.surface_form == "etm"
        assert m.feature_bundle["tense"] == "past"
        assert "PAST" in m.source_keys


class TestPortmanteauRegistryRegisterLookup:
    def test_lookup_returns_none_when_empty(self):
        reg = PortmanteauRegistry()
        assert reg.lookup(frozenset({"PAST", "1SG"})) is None

    def test_register_then_lookup(self):
        reg = PortmanteauRegistry()
        reg.register("PAST", "1SG", "etm", {"tense": "past", "person": "1st"})
        result = reg.lookup(frozenset({"PAST", "1SG"}))
        assert result is not None
        assert result.surface_form == "etm"

    def test_lookup_order_independent(self):
        reg = PortmanteauRegistry()
        reg.register("1SG", "PAST", "etm", {})
        assert reg.lookup(frozenset({"PAST", "1SG"})) is not None

    def test_lookup_different_feature_set_returns_none(self):
        reg = PortmanteauRegistry()
        reg.register("PAST", "1SG", "etm", {})
        assert reg.lookup(frozenset({"PAST", "2SG"})) is None


class TestCooccurrenceTracking:
    def test_track_increments(self):
        reg = PortmanteauRegistry()
        count = reg.track_cooccurrence("PAST", "1SG")
        assert count == 1

    def test_track_cumulative(self):
        reg = PortmanteauRegistry()
        reg.track_cooccurrence("PAST", "1SG")
        reg.track_cooccurrence("PAST", "1SG")
        assert reg.cooccurrence_count("PAST", "1SG") == 2

    def test_track_order_independent(self):
        reg = PortmanteauRegistry()
        reg.track_cooccurrence("1SG", "PAST")
        assert reg.cooccurrence_count("PAST", "1SG") == 1

    def test_different_pairs_tracked_independently(self):
        reg = PortmanteauRegistry()
        reg.track_cooccurrence("PAST", "1SG")
        reg.track_cooccurrence("PAST", "2SG")
        assert reg.cooccurrence_count("PAST", "1SG") == 1
        assert reg.cooccurrence_count("PAST", "2SG") == 1


class TestMaybeFuse:
    def _prime_registry(self, threshold: int = 3) -> PortmanteauRegistry:
        return PortmanteauRegistry(cooccurrence_threshold=threshold)

    def test_does_not_fuse_below_threshold(self):
        reg = self._prime_registry(3)
        reg.track_cooccurrence("PAST", "1SG")
        reg.track_cooccurrence("PAST", "1SG")
        result = reg.maybe_fuse("PAST", "et", "1SG", "m", {"et", "m"})
        assert result is None

    def test_fuses_when_combined_form_collides_with_existing(self):
        reg = self._prime_registry(3)
        for _ in range(3):
            reg.track_cooccurrence("PAST", "1SG")
        result = reg.maybe_fuse("PAST", "et", "1SG", "m", {"etm"})
        assert result is not None
        assert result.surface_form == "etm"

    def test_haplology_reduces_duplicate_segment(self):
        reg = self._prime_registry(3)
        for _ in range(3):
            reg.track_cooccurrence("A", "B")
        result = reg.maybe_fuse("A", "at", "B", "ta", {"ata"})
        assert result is not None
        assert result.surface_form == "ata"

    def test_fused_entry_retrievable_by_lookup(self):
        reg = self._prime_registry(3)
        for _ in range(3):
            reg.track_cooccurrence("PAST", "1SG")
        reg.maybe_fuse("PAST", "et", "1SG", "m", {"etm"})
        assert reg.lookup(frozenset({"PAST", "1SG"})) is not None

    def test_fused_keys_marked_dead(self):
        reg = self._prime_registry(3)
        for _ in range(3):
            reg.track_cooccurrence("PAST", "1SG")
        reg.maybe_fuse("PAST", "et", "1SG", "m", {"etm"})
        assert reg.is_dead("PAST")
        assert reg.is_dead("1SG")

    def test_nonfused_key_not_dead(self):
        reg = self._prime_registry(3)
        assert reg.is_dead("PAST") is False

    def test_second_call_returns_cached_entry(self):
        reg = self._prime_registry(3)
        for _ in range(3):
            reg.track_cooccurrence("PAST", "1SG")
        r1 = reg.maybe_fuse("PAST", "et", "1SG", "m", {"etm"})
        r2 = reg.maybe_fuse("PAST", "et", "1SG", "m", {"etm"})
        assert r1 is r2


class TestLookupPriorityOverConcatenation:
    """Verify that a lookup hit should replace individual suffix concatenation."""

    def test_lookup_surface_form_differs_from_concatenation(self):
        reg = PortmanteauRegistry()
        reg.register("PAST", "1SG", "o", {"tense": "past", "person": "1st"})
        morpheme = reg.lookup(frozenset({"PAST", "1SG"}))
        concatenated = "et" + "m"
        assert morpheme.surface_form != concatenated
        assert morpheme.surface_form == "o"
