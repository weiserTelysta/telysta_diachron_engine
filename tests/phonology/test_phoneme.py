import pytest

from app.domain.phonology.phoneme import Phoneme, PhonemeInventory


def make_minimal_inventory() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


def test_phoneme_matches_full_spec():
    p = Phoneme(
        symbol="p",
        features={
            "syllabic": False, "consonantal": True, "voiced": False,
            "continuant": False, "nasal": False, "sonorant": False,
            "labial": True, "coronal": False, "dorsal": False,
            "high": False, "low": False, "back": False, "round": False,
        },
    )
    assert p.matches({"voiced": False, "labial": True})
    assert not p.matches({"voiced": True})


def test_phoneme_matches_empty_spec():
    p = Phoneme(symbol="x", features={"voiced": True})
    assert p.matches({})


def test_phoneme_apply_change_voicing():
    inv = make_minimal_inventory()
    p_phoneme = inv.find_by_symbol("p")
    assert p_phoneme is not None
    result = p_phoneme.apply_change({"voiced": True}, inv)
    assert result is not None
    assert result.symbol == "b"


def test_phoneme_apply_change_no_match():
    p = Phoneme(
        symbol="p",
        features={"voiced": False, "labial": True, "consonantal": True},
    )
    inv = PhonemeInventory([p])
    result = p.apply_change({"voiced": True}, inv)
    assert result is None


def test_inventory_get_natural_class_voiceless_stops():
    inv = make_minimal_inventory()
    voiceless_stops = inv.get_natural_class({"voiced": False, "consonantal": True, "continuant": False})
    symbols = {p.symbol for p in voiceless_stops}
    assert "p" in symbols
    assert "t" in symbols
    assert "k" in symbols
    assert "b" not in symbols
    assert "a" not in symbols


def test_inventory_get_natural_class_vowels():
    inv = make_minimal_inventory()
    vowels = inv.get_natural_class({"syllabic": True})
    symbols = {p.symbol for p in vowels}
    # Core vowels always present; preset may include additional IPA vowels (e.g. ɛ, ɔ)
    assert {"a", "e", "i", "o", "u"}.issubset(symbols)
    assert all(inv.find_by_symbol(s).features["syllabic"] for s in symbols)


def test_inventory_find_by_symbol():
    inv = make_minimal_inventory()
    p = inv.find_by_symbol("m")
    assert p is not None
    assert p.features["nasal"] is True
    assert p.features["labial"] is True


def test_inventory_find_by_symbol_missing():
    inv = make_minimal_inventory()
    assert inv.find_by_symbol("Q") is None


def test_inventory_find_by_features_exact():
    inv = make_minimal_inventory()
    p_by_sym = inv.find_by_symbol("p")
    assert p_by_sym is not None
    p_by_feat = inv.find_by_features(p_by_sym.features)
    assert p_by_feat is not None
    assert p_by_feat.symbol == "p"


def test_inventory_vowels_property():
    inv = make_minimal_inventory()
    assert len(inv.vowels) >= 5
    for v in inv.vowels:
        assert v.features["syllabic"] is True


def test_inventory_consonants_property():
    inv = make_minimal_inventory()
    for c in inv.consonants:
        assert c.features["syllabic"] is False


def test_inventory_from_preset_elven():
    inv = PhonemeInventory.from_preset("elven_light")
    assert len(inv) > 0
    voiced_stops = inv.get_natural_class({"voiced": True, "consonantal": True, "continuant": False, "nasal": False})
    assert len(voiced_stops) == 0, "Elven preset should have no voiced stops"


def test_inventory_from_preset_orcish():
    inv = PhonemeInventory.from_preset("orcish_heavy")
    short_vowels = inv.get_natural_class({"syllabic": True, "long": False})
    long_vowels = inv.get_natural_class({"syllabic": True, "long": True})
    assert len(short_vowels) == 3, "Orcish preset should have exactly 3 short vowels"
    assert len(long_vowels) == 3, "Orcish preset should have exactly 3 long vowels (aː, uː, ɔː)"
