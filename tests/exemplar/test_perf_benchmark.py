"""Phase 1 exit-criteria performance benchmark.

Spec: 1000 words × 5 exemplars × 10 rules — single-era batch evolution < 1 second.
"""
import time

import numpy as np
import pytest

from app.domain.exemplar.matrix import ExemplarMatrix
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.phonology.rule_compiler import RuleCompiler


_FORMS = ["taka", "mibo", "dɔlu", "peta", "garu", "nima", "bola", "sɛti", "vuka", "rɛna"]
_RULE_DEFS = [
    {
        "name": "final_vowel_drop",
        "priority": 10,
        "op": "delete",
        "target": {"syllabic": True},
        "env_before": None,
        "env_after": None,
        "env_flags": {"word_final": True},
    },
    {
        "name": "intervocalic_voicing",
        "priority": 20,
        "op": "change",
        "target": {"voiced": False, "consonantal": True, "continuant": False},
        "change": {"voiced": True},
        "env_before": {"syllabic": True},
        "env_after": {"syllabic": True},
        "env_flags": {},
    },
    {
        "name": "nasal_assimilation",
        "priority": 30,
        "op": "change",
        "target": {"nasal": True, "coronal": True},
        "change": {"coronal": False, "labial": True},
        "env_before": None,
        "env_after": {"labial": True},
        "env_flags": {},
    },
]


@pytest.fixture(scope="module")
def inventory() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


@pytest.fixture(scope="module")
def large_exemplar_matrix(inventory: PhonemeInventory) -> ExemplarMatrix:
    rng = np.random.default_rng(42)
    entities: list[LexicalEntity] = []
    for i in range(1000):
        form = _FORMS[i % len(_FORMS)]
        exemplars = [
            {"form": form, "weight": float(w)}
            for w in rng.dirichlet(np.ones(5))
        ]
        entities.append(
            LexicalEntity(
                id=f"w{i}",
                concept=f"concept_{i}",
                pos="n.",
                ipa_current=form,
                ipa_history=[],
                frequency_weight=float(rng.uniform(0.001, 0.05)),
                ipa_exemplars=exemplars,
            )
        )
    return ExemplarMatrix.from_lexicon(entities, inventory)


@pytest.fixture(scope="module")
def compiled_rules(inventory: PhonemeInventory):
    compiler = RuleCompiler(inventory)
    return [compiler.compile(r) for r in _RULE_DEFS]


def test_batch_evolution_under_one_second(
    large_exemplar_matrix: ExemplarMatrix,
    compiled_rules,
) -> None:
    """1000 words × 5 exemplars × 10 rule applications must complete in < 1 second."""
    rng = np.random.default_rng(0)
    rules_10 = (compiled_rules * 4)[:10]

    start = time.perf_counter()
    for rule in rules_10:
        large_exemplar_matrix.apply_rule_batch(rule, rng, change_prob=0.5)
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0, (
        f"Phase 1 performance benchmark FAILED: {elapsed:.3f}s >= 1.0s\n"
        f"Matrix shape: {large_exemplar_matrix.matrix.shape}"
    )


def test_matrix_scale(large_exemplar_matrix: ExemplarMatrix) -> None:
    """Sanity: matrix must have >= 1000*5*2 rows (1000 words, 5 exemplars, avg >=2 phonemes)."""
    assert len(large_exemplar_matrix.matrix) >= 1000 * 5 * 2
