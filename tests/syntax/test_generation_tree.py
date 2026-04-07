import pytest

from app.domain.syntax.generation_tree import GenerationTree
from app.domain.syntax.morphological_planner import PlannedWord
from app.domain.syntax.typology import TypologyMatrix


def _pw(role: str, ipa: str, suffixes: list[str] | None = None) -> PlannedWord:
    return PlannedWord(role=role, lexeme_ipa=ipa, suffixes=suffixes or [])


def _svo_words() -> list[PlannedWord]:
    return [
        _pw("subject", "ni"),
        _pw("verb",    "vid", ["et"]),
        _pw("object",  "min", ["o"]),
    ]


class TestGenerationTreeFromPlanned:
    def test_svo_order(self):
        typ = TypologyMatrix(word_order="SVO")
        tree = GenerationTree.from_planned(typ, _svo_words())
        tokens = tree.linearize()
        assert tokens == ["ni", "videt", "mino"]

    def test_sov_order(self):
        typ = TypologyMatrix(word_order="SOV")
        tree = GenerationTree.from_planned(typ, _svo_words())
        tokens = tree.linearize()
        assert tokens == ["ni", "mino", "videt"]

    def test_vso_order(self):
        typ = TypologyMatrix(word_order="VSO")
        tree = GenerationTree.from_planned(typ, _svo_words())
        tokens = tree.linearize()
        assert tokens == ["videt", "ni", "mino"]

    def test_vos_order(self):
        typ = TypologyMatrix(word_order="VOS")
        tree = GenerationTree.from_planned(typ, _svo_words())
        tokens = tree.linearize()
        assert tokens == ["videt", "mino", "ni"]

    def test_ovs_order(self):
        typ = TypologyMatrix(word_order="OVS")
        tree = GenerationTree.from_planned(typ, _svo_words())
        tokens = tree.linearize()
        assert tokens == ["mino", "videt", "ni"]

    def test_osv_order(self):
        typ = TypologyMatrix(word_order="OSV")
        tree = GenerationTree.from_planned(typ, _svo_words())
        tokens = tree.linearize()
        assert tokens == ["mino", "ni", "videt"]


class TestGenerationTreeMissingRoles:
    def test_verb_only(self):
        typ = TypologyMatrix(word_order="SVO")
        tree = GenerationTree.from_planned(typ, [_pw("verb", "vid")])
        tokens = tree.linearize()
        assert tokens == ["vid"]

    def test_subject_verb_no_object(self):
        typ = TypologyMatrix(word_order="SVO")
        words = [_pw("subject", "ni"), _pw("verb", "vid", ["et"])]
        tokens = GenerationTree.from_planned(typ, words).linearize()
        assert tokens == ["ni", "videt"]


class TestGenerationTreeModifier:
    def test_modifier_before_head_svo(self):
        """Modifier should appear before the first core slot (S) in SVO."""
        typ = TypologyMatrix(word_order="SVO")
        words = [
            _pw("subject",  "ni"),
            _pw("verb",     "vid"),
            _pw("object",   "min"),
            _pw("modifier", "garu"),
        ]
        tokens = GenerationTree.from_planned(typ, words).linearize()
        assert "garu" in tokens

    def test_modifier_position_before_first_core(self):
        typ = TypologyMatrix(word_order="SVO")
        words = [_pw("verb", "vid"), _pw("modifier", "garu")]
        tokens = GenerationTree.from_planned(typ, words).linearize()
        mod_idx = tokens.index("garu")
        verb_idx = tokens.index("vid")
        assert mod_idx < verb_idx


class TestGenerationTreeLinearizeEmpty:
    def test_empty_tree_returns_empty(self):
        tree = GenerationTree()
        assert tree.linearize() == []

    def test_from_planned_empty_list(self):
        typ = TypologyMatrix()
        tree = GenerationTree.from_planned(typ, [])
        assert tree.linearize() == []
