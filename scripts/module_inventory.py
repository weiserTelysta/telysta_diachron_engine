"""Report static production reachability and test references for Python modules.

The report intentionally does not infer semantic ownership.  It supplies the
repeatable evidence used by the A-004 migration matrix.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
TESTS = ROOT / "tests"
ENTRYPOINTS = (ROOT / "main.py", ROOT / "streamlit_app.py")


@dataclass(frozen=True)
class ModuleRecord:
    module: str
    path: str
    production_reachable: bool
    imported_by: tuple[str, ...]
    imports: tuple[str, ...]
    test_reference_count: int


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def module_paths() -> dict[str, Path]:
    paths = {module_name(path): path for path in APP.rglob("*.py")}
    paths.update({module_name(path): path for path in ENTRYPOINTS})
    return paths


def _parse_imports(path: Path, known_modules: set[str]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()

    def resolve(candidate: str) -> str | None:
        if candidate in known_modules:
            return candidate
        package_init = f"{candidate}.__init__"
        if package_init in known_modules:
            return package_init
        parts = candidate.split(".")
        while len(parts) > 1:
            parts.pop()
            parent = ".".join(parts)
            if parent in known_modules:
                return parent
            if f"{parent}.__init__" in known_modules:
                return f"{parent}.__init__"
        return None

    for node in ast.walk(tree):
        candidates: list[str] = []
        if isinstance(node, ast.Import):
            candidates = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            candidates = [node.module]
        for candidate in candidates:
            if candidate == "app" or candidate.startswith("app."):
                resolved = resolve(candidate)
                if resolved:
                    imports.add(resolved)
    return imports


def _test_references(known_modules: set[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for path in TESTS.rglob("*.py"):
        for imported in _parse_imports(path, known_modules):
            counts[imported] += 1
    return dict(counts)


def build_inventory() -> dict[str, object]:
    paths = module_paths()
    known_modules = set(paths)
    imports = {module: _parse_imports(path, known_modules) for module, path in paths.items()}
    reverse: dict[str, set[str]] = defaultdict(set)
    for source, targets in imports.items():
        for target in targets:
            reverse[target].add(source)

    reachable: set[str] = set()
    queue = deque(module_name(path) for path in ENTRYPOINTS)
    while queue:
        current = queue.popleft()
        if current in reachable:
            continue
        reachable.add(current)
        queue.extend(sorted(imports.get(current, set()) - reachable))

    test_references = _test_references(known_modules)
    records = [
        ModuleRecord(
            module=module,
            path=path.relative_to(ROOT).as_posix(),
            production_reachable=module in reachable,
            imported_by=tuple(sorted(reverse.get(module, set()))),
            imports=tuple(sorted(imports[module])),
            test_reference_count=test_references.get(module, 0),
        )
        for module, path in sorted(paths.items())
        if module.startswith("app.")
    ]

    return {
        "schema": "telysta.module-inventory.v1",
        "entrypoints": [module_name(path) for path in ENTRYPOINTS],
        "counts": {
            "app_modules": len(records),
            "production_reachable": sum(record.production_reachable for record in records),
            "test_referenced": sum(record.test_reference_count > 0 for record in records),
            "unreachable": sum(not record.production_reachable for record in records),
        },
        "modules": [asdict(record) for record in records],
    }


def _markdown(inventory: dict[str, object]) -> str:
    counts = inventory["counts"]
    assert isinstance(counts, dict)
    lines = [
        "# Module inventory report",
        "",
        f"- schema: `{inventory['schema']}`",
        f"- app modules: {counts['app_modules']}",
        f"- production reachable: {counts['production_reachable']}",
        f"- test referenced: {counts['test_referenced']}",
        f"- unreachable from production entrypoints: {counts['unreachable']}",
        "",
        "| Module | Production reachable | Test references | Imported by |",
        "|---|---:|---:|---|",
    ]
    modules = inventory["modules"]
    assert isinstance(modules, list)
    for record in modules:
        assert isinstance(record, dict)
        imported_by = ", ".join(record["imported_by"]) or "—"
        lines.append(
            f"| `{record['module']}` | {'yes' if record['production_reachable'] else 'no'} | "
            f"{record['test_reference_count']} | {imported_by} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    inventory = build_inventory()
    if args.format == "markdown":
        print(_markdown(inventory))
    else:
        print(json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
