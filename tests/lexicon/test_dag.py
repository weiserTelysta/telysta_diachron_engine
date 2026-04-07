import pytest

from app.domain.lexicon.dag import DAGEdge, WordDAG


def make_dag() -> WordDAG:
    dag = WordDAG()
    dag.add_edge("root", "era1_a", era=1, edge_type="sound_change")
    dag.add_edge("root", "era1_b", era=1, edge_type="borrowing")
    dag.add_edge("era1_a", "era2_a", era=2, edge_type="sound_change")
    return dag


def test_add_node_idempotent() -> None:
    dag = WordDAG()
    dag.add_node("x")
    dag.add_node("x")
    assert len(dag) == 1


def test_add_edge_creates_nodes() -> None:
    dag = WordDAG()
    dag.add_edge("a", "b", era=0, edge_type="sound_change")
    assert len(dag) == 2


def test_add_edge_deduplication() -> None:
    dag = WordDAG()
    dag.add_edge("a", "b", era=1, edge_type="sound_change")
    dag.add_edge("a", "b", era=1, edge_type="sound_change")
    assert len(dag.children("a")) == 1


def test_ancestors() -> None:
    dag = make_dag()
    assert set(dag.ancestors("era2_a")) == {"root", "era1_a"}


def test_ancestors_leaf() -> None:
    dag = make_dag()
    assert dag.ancestors("root") == []


def test_descendants() -> None:
    dag = make_dag()
    assert set(dag.descendants("root")) == {"era1_a", "era1_b", "era2_a"}


def test_descendants_leaf() -> None:
    dag = make_dag()
    assert dag.descendants("era2_a") == []


def test_parents() -> None:
    dag = make_dag()
    assert dag.parents("era1_a") == ["root"]
    assert dag.parents("root") == []


def test_children_edge_type() -> None:
    dag = make_dag()
    children = dag.children("root")
    types = {e.edge_type for e in children}
    assert types == {"sound_change", "borrowing"}


def test_round_trip_serialisation() -> None:
    dag = make_dag()
    d = dag.to_dict()
    restored = WordDAG.from_dict(d)

    assert set(restored.ancestors("era2_a")) == {"root", "era1_a"}
    assert set(restored.descendants("root")) == {"era1_a", "era1_b", "era2_a"}


def test_len() -> None:
    dag = make_dag()
    assert len(dag) == 4  # root, era1_a, era1_b, era2_a
