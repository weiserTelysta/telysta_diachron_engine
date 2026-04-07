import pytest

from app.domain.syntax.csg import (
    CSGEdge,
    CSGNode,
    CSGValidator,
    ControlledSemanticGraph,
)
from app.domain.syntax.semantic_graph import SemanticGraph, SemanticPrime


def _make_prime_graph(*prime_ids: str) -> SemanticGraph:
    g = SemanticGraph()
    for pid in prime_ids:
        g.add_prime(SemanticPrime(id=pid, label_en=pid, category="test", relations=()))
    return g


class TestCSGNodeEdge:
    def test_node_hash_equality(self):
        a = CSGNode(id="n1", prime_id="DO")
        b = CSGNode(id="n1", prime_id="MOVE")
        assert a == b
        assert hash(a) == hash(b)

    def test_node_inequality(self):
        a = CSGNode(id="n1", prime_id="DO")
        b = CSGNode(id="n2", prime_id="DO")
        assert a != b


class TestControlledSemanticGraph:
    def _simple_csg(self) -> ControlledSemanticGraph:
        csg = ControlledSemanticGraph()
        csg.add_node(CSGNode(id="n1", prime_id="SOMEONE"))
        csg.add_node(CSGNode(id="n2", prime_id="DO"))
        csg.add_node(CSGNode(id="n3", prime_id="SOMETHING"))
        csg.add_edge(CSGEdge(from_id="n1", to_id="n2", relation="agent"))
        csg.add_edge(CSGEdge(from_id="n2", to_id="n3", relation="patient"))
        return csg

    def test_add_and_retrieve(self):
        csg = self._simple_csg()
        assert len(csg.nodes) == 3
        assert len(csg.edges) == 2
        assert csg.get_node("n2").prime_id == "DO"

    def test_no_cycle_dag(self):
        csg = self._simple_csg()
        assert not csg.has_cycle()

    def test_cycle_detected(self):
        csg = ControlledSemanticGraph()
        csg.add_node(CSGNode(id="a", prime_id="DO"))
        csg.add_node(CSGNode(id="b", prime_id="MOVE"))
        csg.add_node(CSGNode(id="c", prime_id="HAPPEN"))
        csg.add_edge(CSGEdge(from_id="a", to_id="b", relation="agent"))
        csg.add_edge(CSGEdge(from_id="b", to_id="c", relation="patient"))
        csg.add_edge(CSGEdge(from_id="c", to_id="a", relation="cause"))
        assert csg.has_cycle()

    def test_self_loop_is_cycle(self):
        csg = ControlledSemanticGraph()
        csg.add_node(CSGNode(id="x", prime_id="BE"))
        csg.add_edge(CSGEdge(from_id="x", to_id="x", relation="predicate"))
        assert csg.has_cycle()

    def test_empty_graph_no_cycle(self):
        assert not ControlledSemanticGraph().has_cycle()


class TestCSGValidator:
    def test_valid_csg(self):
        primes = _make_prime_graph("SOMEONE", "DO", "SOMETHING")
        validator = CSGValidator(primes)
        csg = ControlledSemanticGraph()
        csg.add_node(CSGNode(id="n1", prime_id="SOMEONE"))
        csg.add_node(CSGNode(id="n2", prime_id="DO"))
        csg.add_edge(CSGEdge(from_id="n1", to_id="n2", relation="agent"))
        assert validator.validate(csg) == []

    def test_unknown_prime_flagged(self):
        primes = _make_prime_graph("DO")
        validator = CSGValidator(primes)
        csg = ControlledSemanticGraph()
        csg.add_node(CSGNode(id="n1", prime_id="UNICORN"))
        errors = validator.validate(csg)
        assert any("UNICORN" in e for e in errors)

    def test_edge_to_unknown_node_flagged(self):
        primes = _make_prime_graph("DO", "MOVE")
        validator = CSGValidator(primes)
        csg = ControlledSemanticGraph()
        csg.add_node(CSGNode(id="n1", prime_id="DO"))
        csg.add_edge(CSGEdge(from_id="n1", to_id="ghost", relation="patient"))
        errors = validator.validate(csg)
        assert any("ghost" in e for e in errors)

    def test_empty_csg_flagged(self):
        primes = _make_prime_graph("DO")
        validator = CSGValidator(primes)
        errors = validator.validate(ControlledSemanticGraph())
        assert errors

    def test_cycle_flagged(self):
        primes = _make_prime_graph("A", "B")
        validator = CSGValidator(primes)
        csg = ControlledSemanticGraph()
        csg.add_node(CSGNode(id="a", prime_id="A"))
        csg.add_node(CSGNode(id="b", prime_id="B"))
        csg.add_edge(CSGEdge(from_id="a", to_id="b", relation="cause"))
        csg.add_edge(CSGEdge(from_id="b", to_id="a", relation="result"))
        errors = validator.validate(csg)
        assert any("cycle" in e for e in errors)
