"""Hostile-environment tests for the repository's hermetic pytest runner."""

from __future__ import annotations

import os
from pathlib import Path

from scripts.pytest_runner import GUARD_FAILURE_EXIT_CODE, run_pytest


def _write_test(path: Path, contents: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def test_environment_addopts_cannot_turn_execution_into_collection_only(
    tmp_path: Path,
) -> None:
    test_file = _write_test(
        tmp_path / "suite" / "test_sample.py",
        "def test_runs():\n    assert True\n",
    )
    environment = dict(os.environ)
    environment["PYTEST_ADDOPTS"] = "--collect-only"

    result = run_pytest(
        [str(test_file), "-q"],
        base_environment=environment,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.collected == 1
    assert result.executed == 1


def test_explicit_collection_only_is_rejected_as_zero_execution(
    tmp_path: Path,
) -> None:
    test_file = _write_test(
        tmp_path / "suite" / "test_sample.py",
        "def test_would_run():\n    assert True\n",
    )

    result = run_pytest(
        [str(test_file), "--collect-only", "-q"],
        capture_output=True,
    )

    assert result.pytest_returncode == 0
    assert result.returncode == GUARD_FAILURE_EXIT_CODE
    assert result.collected == 1
    assert result.executed == 0
    assert result.failure_reason == "pytest executed zero tests"


def test_explicit_empty_selection_is_rejected(
    tmp_path: Path,
) -> None:
    test_file = _write_test(
        tmp_path / "suite" / "test_sample.py",
        "def test_exists():\n    assert True\n",
    )

    result = run_pytest(
        [str(test_file), "-k", "nonexistent", "-q"],
        capture_output=True,
    )

    assert result.pytest_returncode != 0
    assert result.returncode != 0
    assert result.collected == 0
    assert result.executed == 0


def test_normal_execution_reports_exact_counts(
    tmp_path: Path,
) -> None:
    test_file = _write_test(
        tmp_path / "suite" / "test_sample.py",
        (
            "def test_one():\n"
            "    assert True\n\n"
            "def test_two():\n"
            "    assert 1 + 1 == 2\n"
        ),
    )

    result = run_pytest([str(test_file), "-q"], capture_output=True)

    assert result.returncode == 0, result.stderr
    assert result.collected == 2
    assert result.executed == 2
    assert result.failure_reason is None


def test_plugin_pythonpath_and_coverage_environment_are_sanitized(
    tmp_path: Path,
) -> None:
    injected_path = tmp_path / "injected"
    _write_test(
        injected_path / "hostile_pytest_plugin.py",
        "raise RuntimeError('hostile plugin was imported')\n",
    )
    test_file = _write_test(
        tmp_path / "suite" / "test_environment.py",
        (
            "import os\n"
            "import sys\n\n"
            "def test_environment_is_clean():\n"
            "    assert 'PYTEST_ADDOPTS' not in os.environ\n"
            "    assert 'PYTEST_PLUGINS' not in os.environ\n"
            "    assert 'PYTHONPATH' not in os.environ\n"
            "    assert 'COVERAGE_PROCESS_START' not in os.environ\n"
            "    assert os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'\n"
            f"    assert {str(injected_path)!r} not in sys.path\n"
        ),
    )
    environment = dict(os.environ)
    environment.update(
        {
            "PYTEST_ADDOPTS": "-k nonexistent",
            "PYTEST_PLUGINS": "hostile_pytest_plugin",
            "PYTHONPATH": str(injected_path),
            "COVERAGE_PROCESS_START": str(tmp_path / "hostile.coveragerc"),
        }
    )

    result = run_pytest(
        [str(test_file), "-q"],
        base_environment=environment,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.collected == 1
    assert result.executed == 1
