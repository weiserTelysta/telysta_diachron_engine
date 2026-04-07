from app.domain.lexicon.grammaticalization import StasisDrivenCliticManager
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory


def make_entity(
    word_id: str,
    concept: str,
    ipa: str,
    *,
    pos: str,
    frequency_weight: float,
    word_class: str = "function",
) -> LexicalEntity:
    return LexicalEntity(
        id=word_id,
        concept=concept,
        pos=pos,
        ipa_current=ipa,
        ipa_history=[],
        frequency_weight=frequency_weight,
        word_class=word_class,
    )


def test_stasis_driven_cliticization_promotes_blocked_monosyllable() -> None:
    inventory = PhonemeInventory.from_preset("ipa_minimal")
    manager = StasisDrivenCliticManager(inventory, stasis_threshold=3)
    pronoun = make_entity("1", "I", "ʃu", pos="pron.", frequency_weight=0.04524)
    host = make_entity("86", "eat", "zɛga", pos="verb", frequency_weight=0.003785, word_class="content")

    manager.note_blocked_attempt(pronoun)
    manager.note_blocked_attempt(pronoun)
    manager.note_blocked_attempt(pronoun)

    result = manager.maybe_promote(pronoun, [pronoun, host])

    assert result is not None
    assert result.host_word_id == "86"
    assert result.new_ipa == "ʃ"
    assert result.grammaticalization_stage == 4
    assert result.morpheme_type == "prefix"
    assert result.grammatical_function == "agreement"
    assert pronoun.stasis_counter == 0


def test_non_nucleus_block_profile_is_not_candidate() -> None:
    inventory = PhonemeInventory.from_preset("ipa_minimal")
    manager = StasisDrivenCliticManager(inventory, stasis_threshold=3)
    pronoun = make_entity("2", "you", "fɛl", pos="pron.", frequency_weight=0.022139)

    manager.note_blocked_attempt(pronoun)
    manager.note_blocked_attempt(pronoun)
    manager.note_blocked_attempt(pronoun)

    assert manager.maybe_promote(pronoun, [pronoun]) is None
