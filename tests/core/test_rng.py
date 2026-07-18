from __future__ import annotations

import pytest

from app.core.rng import RNG_TREE_VERSION, RngTree


def test_same_path_restarts_same_python_stream() -> None:
    tree = RngTree(888)
    left_rng = tree.python("genesis", "lexicon")
    right_rng = tree.python("genesis", "lexicon")
    left = [left_rng.random() for _ in range(3)]
    right = [right_rng.random() for _ in range(3)]
    assert left == right


def test_stream_object_advances_normally() -> None:
    rng = RngTree(888).python("era", 1, "sound")
    values = [rng.random() for _ in range(3)]
    assert len(set(values)) == 3


def test_unrelated_path_does_not_perturb_existing_stream() -> None:
    tree = RngTree(42)
    before = [tree.python("branch", "north").random() for _ in range(3)]
    tree.python("new", "unrelated", "module").random()
    after = [tree.python("branch", "north").random() for _ in range(3)]
    assert before == after


def test_child_namespace_matches_full_path() -> None:
    tree = RngTree(42)
    assert tree.child("epoch", 2).seed_for("injection") == tree.seed_for(
        "epoch", 2, "injection"
    )


def test_different_paths_have_different_seeds() -> None:
    tree = RngTree(42)
    assert tree.seed_for("sound") != tree.seed_for("typology")


def test_numpy_stream_is_deterministic() -> None:
    tree = RngTree(7)
    assert tree.numpy("matrix").random(5).tolist() == tree.numpy("matrix").random(5).tolist()


@pytest.mark.parametrize("seed", [-1, 2**64, True, 1.5])
def test_invalid_root_seed_rejected(seed: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        RngTree(seed)  # type: ignore[arg-type]


def test_empty_path_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        RngTree(1).seed_for()


def test_version_is_explicit() -> None:
    assert RNG_TREE_VERSION == "legacy-rng-tree-v1"
