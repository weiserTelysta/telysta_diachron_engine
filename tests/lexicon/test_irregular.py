import random

import pytest

from app.domain.lexicon.irregular import IrregularScarManager, LOCK_THRESHOLD
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory


def make_entity(freq: float, ipa: str = "taka") -> LexicalEntity:
    return LexicalEntity(
        id="w1",
        concept="test",
        pos="n.",
        ipa_current=ipa,
        ipa_history=[],
        frequency_weight=freq,
    )


@pytest.fixture
def inventory() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


@pytest.fixture
def mgr() -> IrregularScarManager:
    return IrregularScarManager()


# ------------------------------------------------------------------
# Lock predicate
# ------------------------------------------------------------------

def test_high_freq_is_locked(mgr: IrregularScarManager) -> None:
    assert mgr.is_locked(make_entity(LOCK_THRESHOLD + 0.01))


def test_low_freq_not_locked(mgr: IrregularScarManager) -> None:
    assert not mgr.is_locked(make_entity(LOCK_THRESHOLD - 0.01))


def test_boundary_not_locked(mgr: IrregularScarManager) -> None:
    assert not mgr.is_locked(make_entity(LOCK_THRESHOLD))


# ------------------------------------------------------------------
# try_scar: unlocked word never scarred
# ------------------------------------------------------------------

def test_unlocked_never_scarred(
    mgr: IrregularScarManager, inventory: PhonemeInventory
) -> None:
    entity = make_entity(LOCK_THRESHOLD - 0.01)
    rng = random.Random(42)
    for _ in range(100):
        result = mgr.try_scar(entity, rng, inventory, scar_prob=1.0)
        assert result is None


# ------------------------------------------------------------------
# try_scar: zero probability → never scarred
# ------------------------------------------------------------------

def test_zero_prob_never_scarred(
    mgr: IrregularScarManager, inventory: PhonemeInventory
) -> None:
    entity = make_entity(LOCK_THRESHOLD + 0.01)
    rng = random.Random(42)
    for _ in range(100):
        result = mgr.try_scar(entity, rng, inventory, scar_prob=0.0)
        assert result is None


# ------------------------------------------------------------------
# try_scar: probability=1 eventually returns a new form (statistical)
# ------------------------------------------------------------------

def test_prob_one_can_scar(
    mgr: IrregularScarManager, inventory: PhonemeInventory
) -> None:
    entity = make_entity(LOCK_THRESHOLD + 0.01, ipa="taka")
    rng = random.Random(0)
    scarred_any = False
    for _ in range(200):
        result = mgr.try_scar(entity, rng, inventory, scar_prob=1.0)
        if result is not None:
            new_ipa, scar_key = result
            assert new_ipa != entity.ipa_current
            assert scar_key != ""
            scarred_any = True
            break
    assert scarred_any, "Expected at least one scar over 200 trials with prob=1.0"


# ------------------------------------------------------------------
# Oscillation prevention
# ------------------------------------------------------------------

def test_scar_log_blocks_reverse_voicing_flip(
    mgr: IrregularScarManager, inventory: PhonemeInventory
) -> None:
    """Once cv_flip:ʃ:ʒ is in scar_log, cv_flip:ʒ:ʃ must be blocked."""
    # Find a voiced/voiceless fricative pair in the inventory
    pairs = []
    for p in inventory.consonants:
        if not p.features.get("syllabic"):
            voiced = p.features.get("voiced", False)
            flipped_features = {**p.features, "voiced": not voiced}
            counterpart = inventory.find_by_features(flipped_features)
            if counterpart and counterpart.symbol != p.symbol:
                pairs.append((p.symbol, counterpart.symbol))
    if not pairs:
        pytest.skip("No voicing-pair consonants in inventory")

    original, flipped = pairs[0]
    entity = make_entity(LOCK_THRESHOLD + 0.01, ipa=flipped)
    # Simulate: the flip from original→flipped was already applied
    entity.scar_log = [f"cv_flip:{original}:{flipped}"]

    rng = random.Random(42)
    for _ in range(200):
        result = mgr.try_scar(entity, rng, inventory, scar_prob=1.0)
        if result is not None:
            new_ipa, scar_key = result
            # The reverse flip (flipped→original) must NOT be the result
            assert new_ipa != original, (
                f"Oscillation detected: {flipped} → {original} despite scar_log blocking"
            )


def test_scar_returns_tuple(
    mgr: IrregularScarManager, inventory: PhonemeInventory
) -> None:
    """try_scar always returns (str, str) | None, never bare str."""
    entity = make_entity(LOCK_THRESHOLD + 0.01, ipa="taka")
    rng = random.Random(1)
    for _ in range(50):
        result = mgr.try_scar(entity, rng, inventory, scar_prob=1.0)
        if result is not None:
            assert isinstance(result, tuple)
            assert len(result) == 2
            new_ipa, scar_key = result
            assert isinstance(new_ipa, str)
            assert isinstance(scar_key, str)
            break
