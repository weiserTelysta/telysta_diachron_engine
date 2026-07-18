from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "module_inventory.py"


def _inventory_module():
    spec = importlib.util.spec_from_file_location("module_inventory", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_inventory_has_current_schema_and_entrypoints() -> None:
    inventory = _inventory_module().build_inventory()
    assert inventory["schema"] == "telysta.module-inventory.v1"
    assert inventory["entrypoints"] == ["main", "streamlit_app"]
    assert inventory["counts"]["app_modules"] >= 80


def test_inventory_marks_engine_session_as_production_reachable() -> None:
    inventory = _inventory_module().build_inventory()
    records = {record["module"]: record for record in inventory["modules"]}
    assert records["app.engine.session"]["production_reachable"] is True
    assert records["app.engine.evolution"]["production_reachable"] is True


def test_inventory_keeps_test_only_matrix_visible() -> None:
    inventory = _inventory_module().build_inventory()
    records = {record["module"]: record for record in inventory["modules"]}
    matrix = records["app.domain.exemplar.matrix"]
    assert matrix["test_reference_count"] > 0
    assert matrix["production_reachable"] is False
