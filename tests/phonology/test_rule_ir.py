import pytest

from app.domain.phonology.ir import SoundChangeRule
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.phonology.rule_compiler import RuleCompiler


def make_compiler() -> RuleCompiler:
    inv = PhonemeInventory.from_preset("ipa_minimal")
    return RuleCompiler(inv)


def test_compile_change_op_output_map():
    compiler = make_compiler()
    rule = compiler.compile({
        "name": "voicing",
        "priority": 10,
        "op": "change",
        "target": {"voiced": False, "consonantal": True, "continuant": False},
        "change": {"voiced": True},
        "env_before": None,
        "env_after": None,
        "env_flags": {},
    })
    assert rule.name == "voicing"
    assert rule.op == "change"
    assert "p" in rule.output_map
    assert rule.output_map["p"] == "b"
    assert rule.output_map["t"] == "d"
    assert rule.output_map["k"] == "g"


def test_compile_delete_op_empty_output_map():
    compiler = make_compiler()
    rule = compiler.compile({
        "name": "final_drop",
        "priority": 5,
        "op": "delete",
        "target": {"syllabic": True},
        "env_before": None,
        "env_after": None,
        "env_flags": {"word_final": True},
    })
    assert rule.op == "delete"
    assert rule.output_map == {}
    assert rule.env_flags.get("word_final") is True


def test_compile_env_before_after_expansion():
    compiler = make_compiler()
    rule = compiler.compile({
        "name": "vv_voicing",
        "priority": 20,
        "op": "change",
        "target": {"voiced": False, "consonantal": True, "continuant": False},
        "change": {"voiced": True},
        "env_before": {"syllabic": True},
        "env_after": {"syllabic": True},
        "env_flags": {},
    })
    assert rule.env_before is not None
    assert rule.env_after is not None
    before_syms = {p.symbol for p in rule.env_before}
    assert "a" in before_syms
    assert "p" not in before_syms


def test_compile_target_class_no_voiced_consonants():
    compiler = make_compiler()
    rule = compiler.compile({
        "name": "devoice",
        "priority": 10,
        "op": "change",
        "target": {"voiced": False, "consonantal": True},
        "change": {"voiced": True},
        "env_before": None,
        "env_after": None,
        "env_flags": {},
    })
    for phoneme in rule.target_class:
        assert phoneme.features["voiced"] is False
        assert phoneme.features["consonantal"] is True


def test_ir_target_symbols_property():
    compiler = make_compiler()
    rule = compiler.compile({
        "name": "test",
        "priority": 1,
        "op": "delete",
        "target": {"syllabic": True},
        "env_before": None,
        "env_after": None,
        "env_flags": {},
    })
    assert {"a", "e", "i", "o", "u"}.issubset(rule.target_symbols)


def test_compile_from_yaml_file():
    from app.core.config import configs
    compiler = make_compiler()
    rules = compiler.compile_file(configs.get_sound_rules_path("basic_rules.yaml"))
    assert len(rules) == 3
    names = [r.name for r in rules]
    assert "final_vowel_drop" in names
    assert "intervocalic_voicing" in names
    assert "nasal_place_assimilation" in names
