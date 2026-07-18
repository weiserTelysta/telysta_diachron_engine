from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.engine.golden import GOLDEN_SCENARIOS, run_legacy_golden_scenario


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "golden" / "legacy_v1.json"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", GOLDEN_SCENARIOS)
def test_golden_scenario_matches_versioned_manifest(
    scenario: str,
    manifest: dict,
    tmp_path: Path,
) -> None:
    result = run_legacy_golden_scenario(scenario, manifest["seed"], tmp_path / scenario)
    expected = manifest["scenarios"][scenario]
    report = result["report"]

    assert result["canonical_schema"] == manifest["canonical_schema"]
    assert result["rng_version"] == manifest["rng_version"]
    assert result["scenario_version"] == manifest["scenario_version"]
    assert report["hashes"]["domains"] == expected["domains"]
    assert report["hashes"]["full"] == expected["full"]
    assert report["hard_errors"] == expected["hard_errors"]
    for field, value in expected["counts"].items():
        assert report["counts"][field] == value


@pytest.mark.parametrize("scenario", GOLDEN_SCENARIOS)
def test_same_seed_is_stable_across_three_runs(scenario: str, tmp_path: Path) -> None:
    hashes = [
        run_legacy_golden_scenario(scenario, 888, tmp_path / f"{scenario}-{index}")["report"]
        ["hashes"]["full"]
        for index in range(3)
    ]
    assert len(set(hashes)) == 1


def test_prior_different_seed_does_not_contaminate_next_run(tmp_path: Path) -> None:
    first = run_legacy_golden_scenario("flat_10", 888, tmp_path / "first")
    different = run_legacy_golden_scenario("flat_10", 999, tmp_path / "different")
    repeated = run_legacy_golden_scenario("flat_10", 888, tmp_path / "repeated")
    assert first["report"]["hashes"]["full"] == repeated["report"]["hashes"]["full"]
    assert first["report"]["hashes"]["full"] != different["report"]["hashes"]["full"]


def test_scenario_order_does_not_change_result(tmp_path: Path) -> None:
    before = run_legacy_golden_scenario("branch", 888, tmp_path / "before")
    run_legacy_golden_scenario("mock_llm", 888, tmp_path / "middle")
    after = run_legacy_golden_scenario("branch", 888, tmp_path / "after")
    assert before["report"]["hashes"]["full"] == after["report"]["hashes"]["full"]


def test_subprocess_result_matches_manifest(manifest: dict) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "baseline_report.py"),
            "--seed",
            str(manifest["seed"]),
            "--scenario",
            "flat_10",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(completed.stdout)
    assert payload[0]["report"]["hashes"]["full"] == manifest["scenarios"]["flat_10"]["full"]
