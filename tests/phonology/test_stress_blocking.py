"""Tests for stress-conditioned and illegal-coda blocking in FinalVowelDropOperator."""
import pytest

from app.domain.phonology.backends.native_backend import NativeBackend
from app.domain.phonology.operators.final_vowel_drop import FinalVowelDropOperator
from app.domain.phonology.phoneme import PhonemeInventory


def make_inventory() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


def make_operator(
    inventory: PhonemeInventory,
    illegal_coda_finals: set[str] | None = None,
) -> FinalVowelDropOperator:
    return FinalVowelDropOperator(
        backend=NativeBackend(),
        inventory=inventory,
        enabled=True,
        era_start=0,
        illegal_coda_finals=illegal_coda_finals,
    )


def test_high_vowel_drops_normally():
    """taki → tak  (high vowel /i/ drops word-finally, no blocking)."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["t", "a", "k", "i"])
    assert result.output == ["t", "a", "k"]
    assert result.changed is True


def test_final_stress_blocks_drop():
    """stress_pattern='final' protects the final vowel from dropping."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["t", "a", "k", "i"], stress_pattern="final")
    assert result.output == ["t", "a", "k", "i"]
    assert result.changed is False


def test_penultimate_stress_allows_drop():
    """stress_pattern='penultimate' does NOT block final vowel drop."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["t", "a", "k", "i"], stress_pattern="penultimate")
    assert result.output == ["t", "a", "k"]
    assert result.changed is True


def test_mono_stress_nucleus_preserved():
    """CV monosyllable: dropping the only vowel would leave no nucleus → blocked."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["t", "i"], stress_pattern="mono")
    assert result.output == ["t", "i"]
    assert result.changed is False


def test_illegal_coda_blocks_drop():
    """If penultimate is dʒ (in illegal_coda_finals), drop is blocked."""
    inv = make_inventory()
    op = make_operator(inv, illegal_coda_finals={"dʒ"})
    # sequence: [d, ʒ, i] — dropping /i/ would expose /dʒ/ as word-final coda
    result = op.apply(["dʒ", "i"])
    assert result.output == ["dʒ", "i"]
    assert result.changed is False


def test_safe_coda_allows_drop():
    """Penultimate /k/ is NOT in illegal_coda_finals → drop proceeds (polysyllabic word)."""
    inv = make_inventory()
    op = make_operator(inv, illegal_coda_finals={"dʒ", "ʒ"})
    # taki → tak; has 'a' nucleus remaining after drop
    result = op.apply(["t", "a", "k", "i"])
    assert result.output == ["t", "a", "k"]
    assert result.changed is True


def test_no_illegal_codas_configured_allows_drop():
    """Empty illegal_coda_finals set → no blocking by coda condition (polysyllabic)."""
    inv = make_inventory()
    op = make_operator(inv, illegal_coda_finals=set())
    # patʃi → patʃ; 'a' remains as nucleus
    result = op.apply(["p", "a", "t", "i"])
    assert result.output == ["p", "a", "t"]
    assert result.changed is True


def test_nucleus_preservation_blocks_drop():
    """Dropping final vowel of a monosyllable would yield bare consonant → blocked."""
    inv = make_inventory()
    op = make_operator(inv)
    # /ʃu/ — 'u' is the only vowel; deletion blocked to preserve nucleus
    result = op.apply(["ʃ", "u"])
    assert result.output == ["ʃ", "u"]
    assert result.changed is False


def test_non_high_vowel_not_targeted():
    """FinalVowelDropOperator targets only high vowels (/i/, /u/).
    Non-high final vowels like /a/, /e/ are not affected by this operator."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["t", "a", "k", "a"])
    # /a/ is not high → should NOT be dropped by this operator
    assert result.output == ["t", "a", "k", "a"]
    assert result.changed is False


def test_operator_disabled():
    inv = make_inventory()
    op = FinalVowelDropOperator(
        backend=NativeBackend(),
        inventory=inv,
        enabled=False,
        era_start=0,
    )
    result = op.apply(["t", "a", "k", "i"])
    assert result.output == ["t", "a", "k", "i"]
    assert result.changed is False
