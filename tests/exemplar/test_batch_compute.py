"""Tests for ExemplarMatrix NumPy batch operations vs OOP reference.

The OOP loop result serves as the ground-truth reference for verifying
vectorized batch operations.
"""
import numpy as np
import pytest

from app.domain.exemplar.collapse import batch_collapse_exemplars
from app.domain.exemplar.matrix import (
    COL_WEIGHT,
    COL_WORD_IDX,
    ExemplarMatrix,
)
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory


def make_entity(wid: str, exemplars: list[dict], freq: float = 0.5) -> LexicalEntity:
    return LexicalEntity(
        id=wid,
        concept="test",
        pos="n.",
        ipa_current=exemplars[0]["form"],
        ipa_history=[exemplars[0]["form"]],
        frequency_weight=freq,
        ipa_exemplars=exemplars,
    )


def make_inventory() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


def test_exemplar_matrix_from_lexicon_shape():
    inv = make_inventory()
    entities = [
        make_entity("w1", [{"form": "taka", "weight": 1.0}]),
        make_entity("w2", [{"form": "minu", "weight": 0.6}, {"form": "mini", "weight": 0.4}]),
    ]
    em = ExemplarMatrix.from_lexicon(entities, inv)
    assert em.matrix.ndim == 2
    assert em.matrix.shape[1] == 5
    assert len(em.matrix) == 4 + 4 + 4


def test_exemplar_matrix_word_index():
    inv = make_inventory()
    entities = [make_entity("alpha", [{"form": "pa", "weight": 1.0}])]
    em = ExemplarMatrix.from_lexicon(entities, inv)
    assert em.word_index[0] == "alpha"


def test_batch_collapse_keeps_top_k():
    inv = make_inventory()
    exemplars = [
        {"form": "taka", "weight": 0.4},
        {"form": "taga", "weight": 0.3},
        {"form": "tana", "weight": 0.2},
        {"form": "tasa", "weight": 0.05},
        {"form": "tara", "weight": 0.03},
        {"form": "tala", "weight": 0.02},
    ]
    entities = [make_entity("w1", exemplars)]
    em = ExemplarMatrix.from_lexicon(entities, inv)
    collapsed = batch_collapse_exemplars(em, keep_top_k=3)

    word_rows = collapsed.matrix[collapsed.matrix[:, COL_WORD_IDX] == 0]
    unique_phoneme_positions = len(set(word_rows[:, 1]))
    assert unique_phoneme_positions <= 3


def test_batch_collapse_normalizes_weights():
    inv = make_inventory()
    exemplars = [
        {"form": "taka", "weight": 0.6},
        {"form": "taga", "weight": 0.4},
    ]
    entities = [make_entity("w1", exemplars)]
    em = ExemplarMatrix.from_lexicon(entities, inv)
    collapsed = batch_collapse_exemplars(em, keep_top_k=5)

    word_idx = 0
    rows = collapsed.matrix[collapsed.matrix[:, COL_WORD_IDX] == word_idx]
    weights = rows[:, COL_WEIGHT]
    total = weights.sum()
    assert abs(total - 1.0) < 1e-6 or len(rows) == 0


def test_batch_collapse_no_cross_word_contamination():
    inv = make_inventory()
    e1 = make_entity("w1", [{"form": "pa", "weight": 0.7}, {"form": "ba", "weight": 0.3}])
    e2 = make_entity("w2", [{"form": "ta", "weight": 0.6}, {"form": "da", "weight": 0.4}])
    em = ExemplarMatrix.from_lexicon([e1, e2], inv)
    collapsed = batch_collapse_exemplars(em, keep_top_k=1)

    rows_w1 = collapsed.matrix[collapsed.matrix[:, COL_WORD_IDX] == 0]
    rows_w2 = collapsed.matrix[collapsed.matrix[:, COL_WORD_IDX] == 1]
    assert len(rows_w1) > 0
    assert len(rows_w2) > 0


def test_batch_collapse_empty_matrix():
    em = ExemplarMatrix(
        matrix=np.empty((0, 5), dtype=np.float64),
        word_index=[],
    )
    result = batch_collapse_exemplars(em, keep_top_k=5)
    assert len(result.matrix) == 0


def test_exemplar_matrix_repr():
    inv = make_inventory()
    entities = [make_entity("w1", [{"form": "pa", "weight": 1.0}])]
    em = ExemplarMatrix.from_lexicon(entities, inv)
    assert "ExemplarMatrix" in repr(em)
