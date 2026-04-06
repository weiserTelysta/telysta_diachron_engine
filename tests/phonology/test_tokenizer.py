import random
from collections import Counter

import pytest

from app.domain.phonology.phoneme import Phoneme, PhonemeInventory


def make_inventory_with_multichars() -> PhonemeInventory:
    """Inventory containing single-char and multi-char IPA symbols."""
    return PhonemeInventory.from_preset("ipa_minimal")


def make_small_inventory() -> PhonemeInventory:
    """Minimal hand-crafted inventory for deterministic tokenizer tests."""
    phonemes = [
        Phoneme("tʃ", {"syllabic": False, "consonantal": True, "voiced": False,
                       "continuant": False, "nasal": False, "sonorant": False,
                       "labial": False, "coronal": True, "dorsal": False,
                       "high": True, "low": False, "back": False, "round": False},
                xsampa="tS", selection_weight=0.5),
        Phoneme("t",  {"syllabic": False, "consonantal": True, "voiced": False,
                       "continuant": False, "nasal": False, "sonorant": False,
                       "labial": False, "coronal": True, "dorsal": False,
                       "high": False, "low": False, "back": False, "round": False},
                xsampa="t", selection_weight=1.0),
        Phoneme("ʃ",  {"syllabic": False, "consonantal": True, "voiced": False,
                       "continuant": True, "nasal": False, "sonorant": False,
                       "labial": False, "coronal": True, "dorsal": False,
                       "high": True, "low": False, "back": False, "round": False},
                xsampa="S", selection_weight=0.7),
        Phoneme("ŋ",  {"syllabic": False, "consonantal": True, "voiced": True,
                       "continuant": False, "nasal": True, "sonorant": True,
                       "labial": False, "coronal": False, "dorsal": True,
                       "high": True, "low": False, "back": True, "round": False},
                xsampa="N", selection_weight=0.6),
        Phoneme("a",  {"syllabic": True, "consonantal": False, "voiced": True,
                       "continuant": True, "nasal": False, "sonorant": True,
                       "labial": False, "coronal": False, "dorsal": True,
                       "high": False, "low": True, "back": False, "round": False},
                xsampa="a", selection_weight=1.0),
        Phoneme("u",  {"syllabic": True, "consonantal": False, "voiced": True,
                       "continuant": True, "nasal": False, "sonorant": True,
                       "labial": False, "coronal": False, "dorsal": True,
                       "high": True, "low": False, "back": True, "round": True},
                xsampa="u", selection_weight=0.9),
        Phoneme("k",  {"syllabic": False, "consonantal": True, "voiced": False,
                       "continuant": False, "nasal": False, "sonorant": False,
                       "labial": False, "coronal": False, "dorsal": True,
                       "high": True, "low": False, "back": True, "round": False},
                xsampa="k", selection_weight=1.0),
    ]
    return PhonemeInventory(phonemes)


# ---------------------------------------------------------------------------
# tokenize tests
# ---------------------------------------------------------------------------

def test_tokenize_single_char():
    inv = make_small_inventory()
    assert inv.tokenize("pata") == ["p", "a", "t", "a"]


def test_tokenize_multi_char_affricate():
    inv = make_small_inventory()
    assert inv.tokenize("tʃaku") == ["tʃ", "a", "k", "u"]


def test_tokenize_mixed_multi_and_single():
    inv = make_small_inventory()
    assert inv.tokenize("tʃaŋu") == ["tʃ", "a", "ŋ", "u"]


def test_tokenize_multi_char_not_split():
    """'tʃ' must not be split into 't' + 'ʃ' when 'tʃ' is in inventory."""
    inv = make_small_inventory()
    tokens = inv.tokenize("tʃa")
    assert tokens[0] == "tʃ", f"Expected 'tʃ' as first token, got {tokens[0]!r}"


def test_tokenize_unknown_char_passthrough():
    """Characters not in inventory are passed through as single-char tokens."""
    inv = make_small_inventory()
    tokens = inv.tokenize("aXu")
    assert tokens == ["a", "X", "u"]


def test_tokenize_empty_string():
    inv = make_small_inventory()
    assert inv.tokenize("") == []


def test_tokenize_roundtrip():
    """join(tokenize(s)) == s for any known-symbol string."""
    inv = make_small_inventory()
    for form in ["tʃaku", "tʃaŋu", "ata", "ku"]:
        assert "".join(inv.tokenize(form)) == form


def test_tokenize_from_preset_with_multi_char():
    inv = make_inventory_with_multichars()
    tokens = inv.tokenize("tʃaŋu")
    assert tokens == ["tʃ", "a", "ŋ", "u"]


# ---------------------------------------------------------------------------
# X-SAMPA tests
# ---------------------------------------------------------------------------

def test_find_by_xsampa_single():
    inv = make_small_inventory()
    p = inv.find_by_xsampa("tS")
    assert p is not None
    assert p.symbol == "tʃ"


def test_find_by_xsampa_missing():
    inv = make_small_inventory()
    assert inv.find_by_xsampa("UNKNOWN") is None


def test_find_by_xsampa_empty_string():
    inv = make_small_inventory()
    assert inv.find_by_xsampa("") is None


def test_xsampa_roundtrip():
    """parse_xsampa_string then join should recover the IPA string."""
    inv = make_small_inventory()
    xsampa_input = "tSaNu"
    ipa_tokens = inv.parse_xsampa_string(xsampa_input)
    assert ipa_tokens == ["tʃ", "a", "ŋ", "u"]
    assert "".join(ipa_tokens) == "tʃaŋu"


def test_parse_xsampa_string_multi_char_code():
    inv = make_small_inventory()
    tokens = inv.parse_xsampa_string("tS")
    assert tokens == ["tʃ"]


def test_parse_xsampa_unknown_passthrough():
    inv = make_small_inventory()
    tokens = inv.parse_xsampa_string("aQu")
    assert tokens == ["a", "Q", "u"]


def test_xsampa_from_minimal_preset():
    inv = make_inventory_with_multichars()
    # X-SAMPA "tS" → IPA "tʃ"
    p = inv.find_by_xsampa("tS")
    assert p is not None and p.symbol == "tʃ"
    # X-SAMPA "E" → IPA "ɛ"
    p2 = inv.find_by_xsampa("E")
    assert p2 is not None and p2.symbol == "ɛ"
    # X-SAMPA "N" → IPA "ŋ"
    p3 = inv.find_by_xsampa("N")
    assert p3 is not None and p3.symbol == "ŋ"


# ---------------------------------------------------------------------------
# Weighted sampling tests
# ---------------------------------------------------------------------------

def test_sample_consonant_returns_consonant():
    inv = make_small_inventory()
    rng = random.Random(0)
    for _ in range(20):
        p = inv.sample_consonant(rng)
        assert not p.features["syllabic"]


def test_sample_vowel_returns_vowel():
    inv = make_small_inventory()
    rng = random.Random(0)
    for _ in range(20):
        p = inv.sample_vowel(rng)
        assert p.features["syllabic"]


def test_weighted_sample_higher_weight_sampled_more():
    """Phoneme with higher selection_weight should appear significantly more often."""
    inv = make_small_inventory()
    # Consonants: tʃ(0.5), t(1.0), ʃ(0.7), ŋ(0.6), k(1.0)
    # 't' and 'k' have the highest weight (1.0); 'tʃ' has the lowest (0.5)
    rng = random.Random(42)
    counts: Counter[str] = Counter()
    n = 2000
    for _ in range(n):
        counts[inv.sample_consonant(rng).symbol] += 1

    # t and k (weight 1.0) should each appear more than tʃ (weight 0.5)
    assert counts["t"] > counts["tʃ"], (
        f"Expected t (w=1.0) > tʃ (w=0.5), got t={counts['t']} tʃ={counts['tʃ']}"
    )
    assert counts["k"] > counts["tʃ"], (
        f"Expected k (w=1.0) > tʃ (w=0.5), got k={counts['k']} tʃ={counts['tʃ']}"
    )


def test_selection_weight_loaded_from_preset():
    inv = make_inventory_with_multichars()
    p = inv.find_by_symbol("tʃ")
    assert p is not None
    assert p.selection_weight == 0.5

    p2 = inv.find_by_symbol("p")
    assert p2 is not None
    assert p2.selection_weight == 1.0
