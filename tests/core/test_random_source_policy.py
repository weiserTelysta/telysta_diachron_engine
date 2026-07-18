from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
RNG_OWNER = (APP / "core" / "rng.py").resolve()

_MODULE_RANDOM_CALLS = {
    "Random",
    "choice",
    "choices",
    "random",
    "randint",
    "randrange",
    "sample",
    "shuffle",
    "uniform",
}


def _qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def test_rng_tree_is_the_only_production_rng_constructor() -> None:
    violations: list[str] = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "random" and path.resolve() != RNG_OWNER:
                relative = path.relative_to(ROOT).as_posix()
                violations.append(f"{relative}:{node.lineno}: from random import ...")
            if not isinstance(node, ast.Call):
                continue
            name = _qualified_name(node.func)
            is_module_random = name.startswith("random.") and name.split(".")[-1] in _MODULE_RANDOM_CALLS
            is_numpy_constructor = name in {"np.random.default_rng", "numpy.random.default_rng"}
            if (is_module_random or is_numpy_constructor) and path.resolve() != RNG_OWNER:
                relative = path.relative_to(ROOT).as_posix()
                violations.append(f"{relative}:{node.lineno}: {name}")

    assert violations == [], "Uncontrolled production RNG calls:\n" + "\n".join(violations)
