"""Tests for natural class expansion and feature-based operations."""
import pytest

from app.domain.phonology.phoneme import Phoneme, PhonemeInventory


def make_inventory() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


def test_all_nasals():
    inv = make_inventory()
    nasals = inv.get_natural_class({"nasal": True})
    symbols = {p.symbol for p in nasals}
    assert symbols == {"m", "n", "ŋ"}


def test_labials():
    inv = make_inventory()
    labials = inv.get_natural_class({"labial": True})
    symbols = {p.symbol for p in labials}
    assert "p" in symbols
    assert "b" in symbols
    assert "m" in symbols
    assert "f" in symbols
    assert "v" in symbols


def test_coronals():
    inv = make_inventory()
    coronals = inv.get_natural_class({"coronal": True})
    symbols = {p.symbol for p in coronals}
    assert "t" in symbols
    assert "d" in symbols
    assert "n" in symbols
    assert "s" in symbols
    assert "z" in symbols
    assert "l" in symbols
    assert "r" in symbols


def test_sonorants():
    inv = make_inventory()
    sonorants = inv.get_natural_class({"sonorant": True})
    for p in sonorants:
        assert p.features["sonorant"] is True
    syms = {p.symbol for p in sonorants}
    assert "p" not in syms
    assert "s" not in syms


def test_voiced_fricatives():
    inv = make_inventory()
    voiced_frics = inv.get_natural_class({"voiced": True, "continuant": True, "consonantal": True})
    symbols = {p.symbol for p in voiced_frics}
    assert "v" in symbols
    assert "z" in symbols
    assert "f" not in symbols


def test_empty_spec_returns_all():
    inv = make_inventory()
    all_phonemes = inv.get_natural_class({})
    assert len(all_phonemes) == len(inv.phonemes)


def test_impossible_spec_returns_empty():
    inv = make_inventory()
    impossible = inv.get_natural_class({"syllabic": True, "consonantal": True})
    assert impossible == []


def test_natural_class_used_in_output_map():
    from app.domain.phonology.rule_compiler import RuleCompiler
    compiler = RuleCompiler(make_inventory())
    rule = compiler.compile({
        "name": "global_voicing",
        "priority": 1,
        "op": "change",
        "target": {"voiced": False, "consonantal": True},
        "change": {"voiced": True},
        "env_before": None,
        "env_after": None,
        "env_flags": {},
    })
    assert rule.output_map.get("p") == "b"
    assert rule.output_map.get("t") == "d"
    assert rule.output_map.get("k") == "g"
    assert rule.output_map.get("f") == "v"
    assert rule.output_map.get("s") == "z"
