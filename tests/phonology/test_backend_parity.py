"""RegexBackend vs NativeBackend output parity tests.

All test cases must produce identical output from both backends,
since NativeBackend is the reference implementation.
"""
import pytest

from app.domain.phonology.backends.native_backend import NativeBackend
from app.domain.phonology.backends.regex_backend import RegexBackend
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.phonology.rule_compiler import RuleCompiler


def make_backends():
    return NativeBackend(), RegexBackend()


def make_compiler():
    inv = PhonemeInventory.from_preset("ipa_minimal")
    return RuleCompiler(inv)


def assert_parity(rule, sequence: list[str]) -> tuple[list[str], list[str]]:
    native, regex = make_backends()
    native_out = native.apply(rule, sequence)
    regex_out = regex.apply(rule, sequence)
    assert native_out == regex_out, (
        f"Parity failure for rule '{rule.name}' on {sequence}:\n"
        f"  NativeBackend → {native_out}\n"
        f"  RegexBackend  → {regex_out}"
    )
    return native_out, regex_out


def test_parity_final_vowel_drop():
    compiler = make_compiler()
    rule = compiler.compile({
        "name": "final_vowel_drop",
        "priority": 10,
        "op": "delete",
        "target": {"syllabic": True},
        "env_before": None,
        "env_after": None,
        "env_flags": {"word_final": True},
    })
    out, _ = assert_parity(rule, ["t", "a", "k", "a"])
    assert out == ["t", "a", "k"]


def test_parity_final_drop_no_vowel():
    compiler = make_compiler()
    rule = compiler.compile({
        "name": "final_vowel_drop",
        "priority": 10,
        "op": "delete",
        "target": {"syllabic": True},
        "env_before": None,
        "env_after": None,
        "env_flags": {"word_final": True},
    })
    out, _ = assert_parity(rule, ["k", "p"])
    assert out == ["k", "p"]


def test_parity_intervocalic_voicing():
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
    out, _ = assert_parity(rule, ["a", "p", "a"])
    assert out == ["a", "b", "a"]


def test_parity_intervocalic_voicing_word_initial_unchanged():
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
    out, _ = assert_parity(rule, ["p", "a", "p", "a"])
    assert out[0] == "p"
    assert out[2] == "b"


def test_parity_empty_sequence():
    compiler = make_compiler()
    rule = compiler.compile({
        "name": "final_vowel_drop",
        "priority": 10,
        "op": "delete",
        "target": {"syllabic": True},
        "env_before": None,
        "env_after": None,
        "env_flags": {"word_final": True},
    })
    out, _ = assert_parity(rule, [])
    assert out == []


def test_parity_no_match():
    compiler = make_compiler()
    rule = compiler.compile({
        "name": "final_vowel_drop",
        "priority": 10,
        "op": "delete",
        "target": {"syllabic": True},
        "env_before": None,
        "env_after": None,
        "env_flags": {"word_final": True},
    })
    out, _ = assert_parity(rule, ["p", "t", "k"])
    assert out == ["p", "t", "k"]
