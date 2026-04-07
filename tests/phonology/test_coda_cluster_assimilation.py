"""Tests for CodaClusterAssimilationOperator (regressive voicing assimilation)."""
import pytest

from app.domain.phonology.backends.native_backend import NativeBackend
from app.domain.phonology.operators.coda_cluster_assimilation import CodaClusterAssimilationOperator
from app.domain.phonology.phoneme import PhonemeInventory


@pytest.fixture
def inv() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


@pytest.fixture
def op(inv: PhonemeInventory) -> CodaClusterAssimilationOperator:
    return CodaClusterAssimilationOperator(
        backend=NativeBackend(),
        inventory=inv,
        enabled=True,
        era_start=0,
    )


def test_voiced_before_voiceless_devoices(op: CodaClusterAssimilationOperator, inv: PhonemeInventory):
    """/bt/ → /pt/: voiced obstruent before voiceless obstruent devoices."""
    # Check if b and t exist in ipa_minimal
    b = inv.find_by_symbol("b")
    t = inv.find_by_symbol("t")
    p = inv.find_by_symbol("p")
    if b is None or t is None or p is None:
        pytest.skip("b/t/p not in ipa_minimal inventory")
    result = op.apply(["b", "t"])
    assert result.output == ["p", "t"]
    assert result.changed is True


def test_voiceless_cluster_unchanged(op: CodaClusterAssimilationOperator, inv: PhonemeInventory):
    """/pt/ → /pt/: already voicing-matched cluster is unchanged."""
    p = inv.find_by_symbol("p")
    t = inv.find_by_symbol("t")
    if p is None or t is None:
        pytest.skip("p/t not in ipa_minimal inventory")
    result = op.apply(["p", "t"])
    assert result.output == ["p", "t"]
    assert result.changed is False


def test_voiced_cluster_unchanged(op: CodaClusterAssimilationOperator, inv: PhonemeInventory):
    """/bd/ → /bd/: both voiced, no change."""
    b = inv.find_by_symbol("b")
    d = inv.find_by_symbol("d")
    if b is None or d is None:
        pytest.skip("b/d not in ipa_minimal inventory")
    result = op.apply(["b", "d"])
    assert result.output == ["b", "d"]
    assert result.changed is False


def test_voiceless_before_voiced_voices(op: CodaClusterAssimilationOperator, inv: PhonemeInventory):
    """/pb/ → /bb/: voiceless before voiced → first obstruent voices."""
    p = inv.find_by_symbol("p")
    b = inv.find_by_symbol("b")
    if p is None or b is None:
        pytest.skip("p/b not in ipa_minimal inventory")
    result = op.apply(["p", "b"])
    assert result.output == ["b", "b"]
    assert result.changed is True


def test_no_cluster_no_change(op: CodaClusterAssimilationOperator, inv: PhonemeInventory):
    """VCV sequence has no adjacent CC → unchanged."""
    result = op.apply(["a", "m", "a"])
    assert result.output == ["a", "m", "a"]
    assert result.changed is False


def test_single_phoneme_unchanged(op: CodaClusterAssimilationOperator):
    """Single-phoneme sequence is returned unchanged."""
    result = op.apply(["p"])
    assert result.output == ["p"]
    assert result.changed is False


def test_era_start_respected(inv: PhonemeInventory):
    """Operator with era_start=5 is not in active_operators_for_era(4)."""
    from app.domain.phonology.operators.registry import OperatorRegistry
    registry = OperatorRegistry()
    op5 = CodaClusterAssimilationOperator(
        backend=NativeBackend(), inventory=inv, era_start=5
    )
    registry.register(op5, enabled=True, priority=25)
    assert op5 not in registry.active_operators_for_era(4)
    assert op5 in registry.active_operators_for_era(5)


def test_sonorant_not_assimilated(op: CodaClusterAssimilationOperator, inv: PhonemeInventory):
    """Sonorants (nasals) are not obstruents and must not trigger assimilation."""
    m = inv.find_by_symbol("m")
    p = inv.find_by_symbol("p")
    if m is None or p is None:
        pytest.skip("m/p not in ipa_minimal inventory")
    result = op.apply(["m", "p"])
    assert result.output == ["m", "p"]
    assert result.changed is False
