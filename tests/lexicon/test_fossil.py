import pytest

from app.domain.lexicon.fossil import (
    FossilPrefixExtractor,
    FOSSIL_FREQ_THRESHOLD,
    FOSSIL_MIN_SYLLABLES,
)
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory


def make_entity(
    ipa: str,
    freq: float = 0.01,
    is_dead: bool = True,
    concept: str = "water",
) -> LexicalEntity:
    return LexicalEntity(
        id="w_water",
        concept=concept,
        pos="n.",
        ipa_current=ipa,
        ipa_history=[],
        frequency_weight=freq,
        is_dead=is_dead,
    )


@pytest.fixture
def inventory() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


@pytest.fixture
def extractor() -> FossilPrefixExtractor:
    return FossilPrefixExtractor()


# ------------------------------------------------------------------
# should_extract guard conditions
# ------------------------------------------------------------------

def test_alive_word_not_extracted(
    extractor: FossilPrefixExtractor, inventory: PhonemeInventory
) -> None:
    entity = make_entity("taka", is_dead=False)
    assert not extractor.should_extract(entity, inventory)


def test_rare_word_not_extracted(
    extractor: FossilPrefixExtractor, inventory: PhonemeInventory
) -> None:
    entity = make_entity("taka", freq=FOSSIL_FREQ_THRESHOLD - 0.0001, is_dead=True)
    assert not extractor.should_extract(entity, inventory)


def test_monosyllable_not_extracted(
    extractor: FossilPrefixExtractor, inventory: PhonemeInventory
) -> None:
    entity = make_entity("ta", is_dead=True)
    assert not extractor.should_extract(entity, inventory)


def test_two_syllable_qualifies(
    extractor: FossilPrefixExtractor, inventory: PhonemeInventory
) -> None:
    entity = make_entity("taka", is_dead=True)
    assert extractor.should_extract(entity, inventory)


# ------------------------------------------------------------------
# extract result structure
# ------------------------------------------------------------------

def test_extract_returns_prefix(
    extractor: FossilPrefixExtractor, inventory: PhonemeInventory
) -> None:
    entity = make_entity("taka")
    fossil = extractor.extract(entity, inventory, current_era=3)
    assert fossil is not None
    assert fossil.morpheme_type == "prefix"
    assert fossil.dag_parent_ids == ["w_water"]
    assert fossil.era_born == 3
    assert not fossil.is_dead


def test_extract_frequency_reduced(
    extractor: FossilPrefixExtractor, inventory: PhonemeInventory
) -> None:
    entity = make_entity("taka", freq=0.01)
    fossil = extractor.extract(entity, inventory, current_era=1)
    assert fossil is not None
    assert fossil.frequency_weight == pytest.approx(0.003)


def test_extract_concept_label(
    extractor: FossilPrefixExtractor, inventory: PhonemeInventory
) -> None:
    entity = make_entity("taka", concept="fire")
    fossil = extractor.extract(entity, inventory, current_era=1)
    assert fossil is not None
    assert fossil.concept == "[fossil:fire]"


def test_extract_first_syllable_cv(
    extractor: FossilPrefixExtractor, inventory: PhonemeInventory
) -> None:
    entity = make_entity("taka")
    fossil = extractor.extract(entity, inventory, current_era=1)
    assert fossil is not None
    assert fossil.ipa_current == "ta"


def test_extract_returns_none_for_ineligible(
    extractor: FossilPrefixExtractor, inventory: PhonemeInventory
) -> None:
    entity = make_entity("ta", is_dead=True)
    assert extractor.extract(entity, inventory, current_era=1) is None
