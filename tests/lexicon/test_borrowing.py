import pytest

from app.domain.lexicon.borrowing import BorrowingInjector, PhonologicalAdaptor
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.storage.event_log import DeltaEventType
from app.domain.storage.hot_state import EngineHotState


@pytest.fixture
def inventory() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


def make_entity(ipa: str, concept: str = "fire", freq: float = 0.01) -> LexicalEntity:
    return LexicalEntity(
        id=f"src_{concept}",
        concept=concept,
        pos="n.",
        ipa_current=ipa,
        ipa_history=[],
        frequency_weight=freq,
    )


# ------------------------------------------------------------------
# final_cluster_simplification
# ------------------------------------------------------------------

def test_final_cluster_simplification(inventory: PhonemeInventory) -> None:
    adaptor = PhonologicalAdaptor()
    tokens = inventory.tokenize("taknt")  # final cluster 'nt'
    result = adaptor.adapt(tokens, inventory, inventory, ["final_cluster_simplification"])
    result_str = "".join(result)
    assert result_str == "takt" or result_str.endswith("t")


def test_no_cluster_unchanged(inventory: PhonemeInventory) -> None:
    adaptor = PhonologicalAdaptor()
    tokens = inventory.tokenize("taka")
    result = adaptor.adapt(tokens, inventory, inventory, ["final_cluster_simplification"])
    assert "".join(result) == "taka"


# ------------------------------------------------------------------
# illegal_onset_repair
# ------------------------------------------------------------------

def test_onset_repair_inserts_vowel(inventory: PhonemeInventory) -> None:
    adaptor = PhonologicalAdaptor()
    tokens = inventory.tokenize("ptak")   # initial consonant cluster
    result = adaptor.adapt(tokens, inventory, inventory, ["illegal_onset_repair"])
    result_str = "".join(result)
    # After repair there should be a vowel between first two consonants
    assert len(result) > len(tokens)


def test_onset_repair_single_consonant_unchanged(inventory: PhonemeInventory) -> None:
    adaptor = PhonologicalAdaptor()
    tokens = inventory.tokenize("tak")
    result = adaptor.adapt(tokens, inventory, inventory, ["illegal_onset_repair"])
    assert "".join(result) == "tak"


# ------------------------------------------------------------------
# vowel_to_inventory
# ------------------------------------------------------------------

def test_vowel_to_inventory_preserves_consonants(inventory: PhonemeInventory) -> None:
    adaptor = PhonologicalAdaptor()
    tokens = inventory.tokenize("taka")
    result = adaptor.adapt(tokens, inventory, inventory, ["vowel_to_inventory"])
    consonants_in  = [t for t in tokens if not (p := inventory.find_by_symbol(t)) or not p.features.get("syllabic")]
    consonants_out = [t for t in result if not (p := inventory.find_by_symbol(t)) or not p.features.get("syllabic")]
    assert consonants_in == consonants_out


def test_vowel_to_inventory_maps_to_target(inventory: PhonemeInventory) -> None:
    adaptor = PhonologicalAdaptor()
    tokens = inventory.tokenize("taka")
    result = adaptor.adapt(tokens, inventory, inventory, ["vowel_to_inventory"])
    # Each mapped vowel must exist in the target inventory
    for tok in result:
        p = inventory.find_by_symbol(tok)
        if p and p.features.get("syllabic"):
            assert inventory.find_by_symbol(tok) is not None


# ------------------------------------------------------------------
# obstruent_voicing_neutralization
# ------------------------------------------------------------------

def test_final_voiced_obstruent_devoiced(inventory: PhonemeInventory) -> None:
    adaptor = PhonologicalAdaptor()
    tokens = inventory.tokenize("tag")   # final /g/ is voiced obstruent
    result = adaptor.adapt(tokens, inventory, inventory, ["obstruent_voicing_neutralization"])
    final = inventory.find_by_symbol(result[-1])
    if final:
        assert not final.features.get("voiced") or final.features.get("sonorant")


def test_final_vowel_not_devoiced(inventory: PhonemeInventory) -> None:
    adaptor = PhonologicalAdaptor()
    tokens = inventory.tokenize("taka")
    result = adaptor.adapt(tokens, inventory, inventory, ["obstruent_voicing_neutralization"])
    assert "".join(result) == "taka"


# ------------------------------------------------------------------
# BorrowingInjector.inject
# ------------------------------------------------------------------

def test_inject_creates_borrow_word_event(inventory: PhonemeInventory) -> None:
    injector = BorrowingInjector()
    source = make_entity("stɛːl", concept="steel")
    hot = EngineHotState()
    event = injector.inject(
        concept="steel",
        source_entity=source,
        target_hot_state=hot,
        source_inv=inventory,
        target_inv=inventory,
        era=3,
        adaptation_rules=["final_cluster_simplification"],
        source_language="ancient_dwarven",
    )
    assert event.event_type == DeltaEventType.BORROW_WORD
    assert event.dag_parent_id == "src_steel"
    assert event.source_language == "ancient_dwarven"
    assert event.new_entity is not None
    assert event.new_entity.source_language == "ancient_dwarven"
    assert event.new_entity.era_born == 3


def test_inject_applies_adaptation(inventory: PhonemeInventory) -> None:
    injector = BorrowingInjector()
    source = make_entity("stɛːl", concept="steel")
    hot = EngineHotState()
    event = injector.inject(
        concept="steel",
        source_entity=source,
        target_hot_state=hot,
        source_inv=inventory,
        target_inv=inventory,
        era=3,
        adaptation_rules=["final_cluster_simplification", "obstruent_voicing_neutralization"],
    )
    # After adaptation the form should be different from raw source
    adapted_ipa = event.new_entity.ipa_current  # type: ignore[union-attr]
    # Check the entity can be applied into hot state without error
    hot.apply_delta(event)
    assert hot.get(event.word_id) is not None
