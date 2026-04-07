import random

import pytest

from app.domain.language.branch import BranchConfig, BranchLanguage
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.backends.native_backend import NativeBackend
from app.domain.phonology.operators.final_vowel_drop import FinalVowelDropOperator
from app.domain.phonology.operators.registry import OperatorRegistry
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.csg import CSGEdge, CSGNode, ControlledSemanticGraph
from app.domain.syntax.semantic_graph import SemanticGraph, SemanticPrime
from app.domain.syntax.typology import TypologyMatrix


def _inv() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


def _registry(inv: PhonemeInventory, enabled: bool = True) -> OperatorRegistry:
    backend = NativeBackend()
    op = FinalVowelDropOperator(backend=backend, inventory=inv, era_start=0)
    reg = OperatorRegistry()
    reg.register(op, enabled=enabled, priority=10)
    return reg


def _prime_graph() -> SemanticGraph:
    g = SemanticGraph()
    for pid in ["I", "SEE", "MAN"]:
        g.add_prime(SemanticPrime(id=pid, label_en=pid.lower(),
                                  category="test", relations=()))
    return g


def _entity(concept: str, pos: str, ipa: str) -> LexicalEntity:
    return LexicalEntity(
        id=concept.lower(), concept=concept, pos=pos,
        ipa_current=ipa, ipa_history=[], frequency_weight=0.5,
    )


def _hot_state(*entities: LexicalEntity) -> EngineHotState:
    hs = EngineHotState()
    for e in entities:
        hs.put(e)
    return hs


def _base_typology() -> TypologyMatrix:
    return TypologyMatrix(
        word_order="SVO",
        case_system="none",
        tense_system="tenseless",
        agreement_features=[],
    )


def _svo_csg() -> ControlledSemanticGraph:
    csg = ControlledSemanticGraph()
    csg.add_node(CSGNode(id="subj", prime_id="I",   attributes={"person": "1"}))
    csg.add_node(CSGNode(id="pred", prime_id="SEE",  attributes={}))
    csg.add_node(CSGNode(id="obj",  prime_id="MAN",  attributes={}))
    csg.add_edge(CSGEdge(from_id="subj", to_id="pred", relation="agent"))
    csg.add_edge(CSGEdge(from_id="pred", to_id="obj",  relation="patient"))
    return csg


class TestBranchCreation:
    def test_branch_clones_hot_state(self):
        inv = _inv()
        parent = _hot_state(_entity("I", "pron.", "ni"), _entity("SEE", "v.", "vid"))
        config = BranchConfig(name="dialect_a", fork_era=0)
        branch = BranchLanguage(config, parent, _base_typology(), _prime_graph(), _registry(inv), inv)

        branch.hot_state.get("i").ipa_current = "CHANGED"
        assert parent.get("i").ipa_current == "ni"

    def test_branch_name_from_config(self):
        inv = _inv()
        hs = _hot_state(_entity("I", "pron.", "ni"))
        config = BranchConfig(name="forest_dialect", fork_era=2)
        branch = BranchLanguage(config, hs, _base_typology(), _prime_graph(), _registry(inv), inv)
        assert branch.name == "forest_dialect"

    def test_initial_era_from_parent(self):
        inv = _inv()
        hs = EngineHotState(current_era=3)
        hs.put(_entity("I", "pron.", "ni"))
        config = BranchConfig(name="b", fork_era=3)
        branch = BranchLanguage(config, hs, _base_typology(), _prime_graph(), _registry(inv), inv)
        assert branch.current_era == 3

    def test_typology_override_applied(self):
        inv = _inv()
        hs = _hot_state(_entity("I", "pron.", "ni"))
        override = TypologyMatrix(word_order="SOV", case_system="none",
                                  tense_system="tenseless", agreement_features=[])
        config = BranchConfig(name="b", fork_era=0, typology_override=override)
        branch = BranchLanguage(config, hs, _base_typology(), _prime_graph(), _registry(inv), inv)
        assert branch.typology.word_order == "SOV"

    def test_typology_deepcopied_if_no_override(self):
        inv = _inv()
        hs = _hot_state(_entity("I", "pron.", "ni"))
        base = _base_typology()
        config = BranchConfig(name="b", fork_era=0)
        branch = BranchLanguage(config, hs, base, _prime_graph(), _registry(inv), inv)
        base.word_order = "VSO"  # type: ignore[assignment]
        assert branch.typology.word_order == "SVO"


class TestBranchEvolveOneEra:
    def test_era_advances(self):
        inv = _inv()
        hs = _hot_state(_entity("I", "pron.", "ni"), _entity("SEE", "v.", "vidi"))
        config = BranchConfig(name="b", fork_era=0)
        branch = BranchLanguage(config, hs, _base_typology(), _prime_graph(), _registry(inv), inv)
        branch.evolve_one_era(rng=random.Random(42))
        assert branch.current_era == 1

    def test_high_final_vowel_can_drop(self):
        inv = _inv()
        hs = _hot_state(_entity("SEE", "v.", "vidi"))
        config = BranchConfig(name="b", fork_era=0)
        branch = BranchLanguage(config, hs, _base_typology(), _prime_graph(), _registry(inv), inv)
        branch.evolve_one_era(rng=random.Random(0))
        see = branch.hot_state.get("see")
        assert see.ipa_current in ("vid", "vidi")

    def test_parent_state_unchanged_after_branch_evolves(self):
        inv = _inv()
        parent = _hot_state(
            _entity("I", "pron.", "ni"),
            _entity("SEE", "v.", "vidi"),
        )
        config = BranchConfig(name="b", fork_era=0)
        branch = BranchLanguage(config, parent, _base_typology(), _prime_graph(), _registry(inv), inv)
        for _ in range(3):
            branch.evolve_one_era(rng=random.Random(99))
        assert parent.get("see").ipa_current == "vidi"

    def test_no_ops_registry_returns_zero_changes(self):
        inv = _inv()
        hs = _hot_state(_entity("SEE", "v.", "vidi"))
        config = BranchConfig(name="b", fork_era=0)
        branch = BranchLanguage(config, hs, _base_typology(), _prime_graph(),
                                OperatorRegistry(), inv)
        changed = branch.evolve_one_era(rng=random.Random(0))
        assert changed == 0


class TestBranchGenerate:
    def test_generate_returns_result(self):
        inv = _inv()
        hs = _hot_state(
            _entity("I",   "pron.", "ni"),
            _entity("SEE", "v.",    "vid"),
            _entity("MAN", "n.",    "min"),
        )
        config = BranchConfig(name="b", fork_era=0)
        branch = BranchLanguage(config, hs, _base_typology(), _prime_graph(), _registry(inv), inv)
        result = branch.generate(_svo_csg())
        assert result.sentence.strip() != ""

    def test_two_branches_diverge_after_evolution(self):
        inv = _inv()
        parent = _hot_state(
            _entity("I",   "pron.", "ni"),
            _entity("SEE", "v.",    "vidi"),
            _entity("MAN", "n.",    "minu"),
        )
        primes = _prime_graph()
        typ_a = TypologyMatrix(word_order="SVO", case_system="none",
                               tense_system="tenseless", agreement_features=[])
        typ_b = TypologyMatrix(word_order="SOV", case_system="none",
                               tense_system="tenseless", agreement_features=[])

        reg = _registry(inv)
        branch_a = BranchLanguage(BranchConfig("A", 0), parent, typ_a, primes, reg, inv)
        branch_b = BranchLanguage(BranchConfig("B", 0, typology_override=typ_b), parent, typ_a, primes, reg, inv)

        for _ in range(3):
            branch_a.evolve_one_era(rng=random.Random(1))
            branch_b.evolve_one_era(rng=random.Random(999))

        csg = _svo_csg()
        result_a = branch_a.generate(csg)
        result_b = branch_b.generate(csg)

        assert result_a.sentence != result_b.sentence

    def test_repr_contains_name_and_era(self):
        inv = _inv()
        hs = _hot_state(_entity("I", "pron.", "ni"))
        config = BranchConfig(name="forest", fork_era=0)
        branch = BranchLanguage(config, hs, _base_typology(), _prime_graph(), _registry(inv), inv)
        r = repr(branch)
        assert "forest" in r
        assert "era=0" in r
