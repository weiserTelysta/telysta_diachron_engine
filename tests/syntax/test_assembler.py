import random

import pytest

from app.domain.lexicon.models import LexicalEntity
from app.domain.syntax.assembler import SentenceAssembler


def _make_entity(id_: str, concept: str, pos: str, ipa: str) -> LexicalEntity:
    return LexicalEntity(
        id=id_, concept=concept, pos=pos,
        ipa_current=ipa, ipa_history=[],
        frequency_weight=0.01,
    )


@pytest.fixture()
def small_lexicon() -> list[LexicalEntity]:
    return [
        _make_entity("w1", "sun",   "n.",   "taka"),
        _make_entity("w2", "water", "n.",   "mibo"),
        _make_entity("w3", "I",     "pron.", "ni"),
        _make_entity("w4", "see",   "v.",   "dɔlu"),
        _make_entity("w5", "give",  "v.",   "peta"),
        _make_entity("w6", "big",   "adj.", "garu"),
    ]


def test_assemble_count(small_lexicon: list[LexicalEntity]) -> None:
    assembler = SentenceAssembler(small_lexicon)
    sentences = assembler.assemble(n=10, rng=random.Random(42))
    assert len(sentences) == 10


def test_assemble_non_empty(small_lexicon: list[LexicalEntity]) -> None:
    assembler = SentenceAssembler(small_lexicon)
    sentences = assembler.assemble(n=5, rng=random.Random(0))
    for s in sentences:
        assert len(s) > 0, "每句不得为空字符串"


def test_assemble_ipa_only_known_chars(small_lexicon: list[LexicalEntity]) -> None:
    """每句中出现的 IPA 字符必须来自词库词形（外加空格分隔符）。"""
    assembler = SentenceAssembler(small_lexicon)
    all_ipa_chars = set("".join(e.ipa_current for e in small_lexicon)) | {" "}
    sentences = assembler.assemble(n=10, rng=random.Random(7))
    for s in sentences:
        for ch in s:
            assert ch in all_ipa_chars, f"意外字符 {ch!r} 出现在句子 {s!r} 中"


def test_assemble_dead_words_excluded() -> None:
    entities = [
        _make_entity("alive", "sun",  "n.", "taka"),
        LexicalEntity(
            id="dead", concept="stone", pos="n.", ipa_current="bol",
            ipa_history=[], frequency_weight=0.01, is_dead=True,
        ),
        _make_entity("verb1", "go",   "v.", "mi"),
    ]
    assembler = SentenceAssembler(entities)
    sentences = assembler.assemble(n=20, rng=random.Random(1))
    for s in sentences:
        assert "bol" not in s, "已死词 'bol' 不应出现在拼接句中"


def test_assemble_deterministic(small_lexicon: list[LexicalEntity]) -> None:
    a = SentenceAssembler(small_lexicon).assemble(n=10, rng=random.Random(99))
    b = SentenceAssembler(small_lexicon).assemble(n=10, rng=random.Random(99))
    assert a == b
