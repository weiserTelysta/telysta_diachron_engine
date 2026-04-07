import pytest

from app.domain.phonology.backends.native_backend import NativeBackend
from app.domain.phonology.operators.final_vowel_drop import FinalVowelDropOperator
from app.domain.phonology.operators.registry import OperatorRegistry
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.syntax.surface_phonology import SurfacePhonologyApplier


def _minimal_inventory() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


def _applier_with_final_vowel_drop() -> tuple[SurfacePhonologyApplier, OperatorRegistry]:
    inv = _minimal_inventory()
    backend = NativeBackend()
    op = FinalVowelDropOperator(backend=backend, inventory=inv, era_start=0)
    registry = OperatorRegistry()
    registry.register(op, enabled=True, priority=10)
    applier = SurfacePhonologyApplier(registry=registry, inventory=inv)
    return applier, registry


class TestSurfacePhonologyApplierPassThrough:
    def test_empty_input(self):
        applier, _ = _applier_with_final_vowel_drop()
        assert applier.apply([]) == []

    def test_empty_token_preserved(self):
        applier, _ = _applier_with_final_vowel_drop()
        result = applier.apply([""])
        assert result == [""]

    def test_no_operator_passthrough(self):
        inv = _minimal_inventory()
        registry = OperatorRegistry()
        applier = SurfacePhonologyApplier(registry=registry, inventory=inv)
        tokens = ["taka", "mibo"]
        assert applier.apply(tokens) == ["taka", "mibo"]


class TestSurfacePhonologyApplierFinalVowelDrop:
    def setup_method(self):
        self.applier, _ = _applier_with_final_vowel_drop()

    def test_high_final_vowel_dropped(self):
        result = self.applier.apply(["taki"])
        assert result == ["tak"]

    def test_non_high_vowel_preserved(self):
        result = self.applier.apply(["taka"])
        assert result == ["taka"]

    def test_multiple_tokens_independently(self):
        result = self.applier.apply(["taki", "minu"])
        assert result[0] == "tak"
        assert result[1] == "min"

    def test_consonant_final_unchanged(self):
        result = self.applier.apply(["tak"])
        assert result == ["tak"]

    def test_token_count_preserved(self):
        tokens = ["taki", "vid", "minu"]
        result = self.applier.apply(tokens)
        assert len(result) == 3


class TestSurfacePhonologyApplierDisabledOperator:
    def test_disabled_operator_no_change(self):
        inv = _minimal_inventory()
        backend = NativeBackend()
        op = FinalVowelDropOperator(backend=backend, inventory=inv, era_start=0)
        registry = OperatorRegistry()
        registry.register(op, enabled=False, priority=10)
        applier = SurfacePhonologyApplier(registry=registry, inventory=inv)
        result = applier.apply(["taki"])
        assert result == ["taki"]
