"""Tests for CompensatoryLengtheningOperator."""
import pytest

from app.domain.phonology.backends.native_backend import NativeBackend
from app.domain.phonology.operators.compensatory_lengthening import CompensatoryLengtheningOperator
from app.domain.phonology.phoneme import PhonemeInventory


def make_inventory() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


def make_operator(inventory: PhonemeInventory) -> CompensatoryLengtheningOperator:
    return CompensatoryLengtheningOperator(
        backend=NativeBackend(),
        inventory=inventory,
        enabled=True,
        era_start=0,
    )


def test_cvc_sonorant_coda_lengthens():
    """bol → boː (word-final sonorant deleted, preceding vowel lengthened)."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["b", "o", "l"])
    assert result.output == ["b", "oː"]
    assert result.changed is True


def test_cvc_nasal_coda_lengthens():
    """ten → teː (word-final nasal deleted, mid vowel lengthened)."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["t", "e", "n"])
    assert result.output == ["t", "eː"]
    assert result.changed is True


def test_cvc_liquid_coda_with_high_vowel():
    """bir → biː."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["b", "i", "r"])
    assert result.output == ["b", "iː"]
    assert result.changed is True


def test_word_ending_in_obstruent_no_change():
    """bot → bot (word-final obstruent is NOT a sonorant; no lengthening)."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["b", "o", "t"])
    assert result.output == ["b", "o", "t"]
    assert result.changed is False


def test_open_syllable_no_change():
    """bo → bo (ends in vowel; no consonant to trigger lengthening)."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["b", "o"])
    assert result.output == ["b", "o"]
    assert result.changed is False


def test_already_long_vowel_no_change():
    """boːl — penultimate is already long; operator should not fire
    (long feature is True, not False, so the blocking condition applies)."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["b", "oː", "l"])
    # oː already has long=True, so no lengthening should happen
    assert result.output == ["b", "oː", "l"]
    assert result.changed is False


def test_single_phoneme_no_crash():
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["a"])
    assert result.output == ["a"]
    assert result.changed is False


def test_operator_disabled():
    inv = make_inventory()
    op = CompensatoryLengtheningOperator(
        backend=NativeBackend(),
        inventory=inv,
        enabled=False,
        era_start=0,
    )
    result = op.apply(["b", "o", "l"])
    assert result.output == ["b", "o", "l"]
    assert result.changed is False


def test_stress_pattern_does_not_block_lengthening():
    """Compensatory lengthening is not blocked by stress; it's a phonological repair."""
    inv = make_inventory()
    op = make_operator(inv)
    result = op.apply(["b", "o", "l"], stress_pattern="final")
    assert result.output == ["b", "oː"]
    assert result.changed is True
