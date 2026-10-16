"""Keep client orchestration above the Rust domain and storage authorities."""

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[2]


def _production_graph() -> dict[str, set[str]]:
    workspace = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))
    graph = {}
    for relative in workspace["workspace"]["members"]:
        manifest = tomllib.loads((ROOT / relative / "Cargo.toml").read_text(encoding="utf-8"))
        tables = [manifest]
        tables.extend(manifest.get("target", {}).values())
        names = set()
        for table in tables:
            for kind in ("dependencies", "build-dependencies"):
                for name, spec in table.get(kind, {}).items():
                    names.add(spec.get("package", name) if isinstance(spec, dict) else name)
        graph[manifest["package"]["name"]] = names
    return graph


def _reachable(graph: dict[str, set[str]], root: str) -> set[str]:
    visited = set()
    pending = list(graph[root])
    while pending:
        name = pending.pop()
        if name not in visited:
            visited.add(name)
            pending.extend(graph.get(name, ()))
    return visited


def test_desktop_reaches_project_storage_through_application() -> None:
    graph = _production_graph()
    assert "telysta-application" in graph["telysta-desktop"]
    assert "telysta-storage" not in graph["telysta-desktop"]
    assert {"telysta-core", "telysta-storage"} <= graph["telysta-application"]


def test_domain_and_storage_do_not_depend_back_on_clients() -> None:
    graph = _production_graph()
    assert not {"telysta-application", "telysta-storage", "telysta-desktop", "tauri", "tokio"} & _reachable(graph, "telysta-core")
    assert not {"telysta-application", "telysta-desktop", "tauri"} & _reachable(graph, "telysta-storage")
    assert not {"telysta-desktop", "tauri"} & _reachable(graph, "telysta-application")
