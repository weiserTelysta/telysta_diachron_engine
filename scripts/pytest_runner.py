"""Run pytest in an isolated subprocess and prove that tests actually ran.

This module is the repository's only supported Python test runner.  The outer
process creates a fresh metrics sidecar and starts an isolated Python
interpreter.  The inner process disables third-party plugin autoloading,
executes pytest with a trusted in-memory plugin, and atomically records the
selected and executed item counts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
METRICS_SCHEMA = "telysta-hermetic-pytest-run.v1"
GUARD_FAILURE_EXIT_CODE = 86
_BOOTSTRAP_FLAG = "--_telysta-hermetic-bootstrap"


@dataclass(frozen=True)
class PytestRunResult:
    """Result of a hermetic pytest invocation."""

    command: tuple[str, ...]
    pytest_returncode: int
    returncode: int
    collected: int | None
    executed: int | None
    failure_reason: str | None
    stdout: str | None = None
    stderr: str | None = None

    @property
    def passed(self) -> bool:
        return self.returncode == 0

    def summary(self) -> str:
        collected = "unknown" if self.collected is None else str(self.collected)
        executed = "unknown" if self.executed is None else str(self.executed)
        return (
            "Hermetic pytest result: "
            f"collected={collected}, executed={executed}, "
            f"pytest_exit={self.pytest_returncode}"
        )


def hermetic_environment(
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    environment = dict(os.environ if base_environment is None else base_environment)
    for key in tuple(environment):
        normalized = key.upper()
        if (
            normalized.startswith("PYTEST_")
            or normalized.startswith("COVERAGE_")
            or normalized
            in {
                "PYTHONHOME",
                "PYTHONINSPECT",
                "PYTHONPATH",
                "PYTHONSTARTUP",
                "PYTHONUSERBASE",
            }
        ):
            environment.pop(key, None)

    # The bootstrap also sets this before importing pytest.  Setting it here
    # makes the subprocess contract explicit to launchers and child processes.
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def _read_metrics(path: Path) -> tuple[int, int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != METRICS_SCHEMA:
        raise ValueError("unexpected pytest metrics schema")

    values = tuple(payload.get(key) for key in ("collected", "executed", "pytestExitCode"))
    if any(type(value) is not int for value in values):
        raise ValueError("pytest metrics counts and exit code must be integers")

    collected, executed, pytest_exit_code = values
    if collected < 0 or executed < 0 or executed > collected:
        raise ValueError("pytest metrics contain impossible item counts")
    return collected, executed, pytest_exit_code


def run_pytest(
    pytest_arguments: Sequence[str],
    *,
    cwd: Path | str = ROOT,
    base_environment: Mapping[str, str] | None = None,
    capture_output: bool = False,
) -> PytestRunResult:
    """Run pytest hermetically and fail closed unless at least one test executes."""

    with tempfile.TemporaryDirectory(prefix="telysta-pytest-") as temporary_directory:
        metrics_path = Path(temporary_directory) / "metrics.json"
        command = (
            sys.executable,
            "-I",
            str(Path(__file__).resolve()),
            _BOOTSTRAP_FLAG,
            str(metrics_path),
            "--",
            "-p",
            "no:cacheprovider",
            *(str(argument) for argument in pytest_arguments),
        )
        completed = subprocess.run(
            command,
            check=False,
            cwd=Path(cwd),
            env=hermetic_environment(base_environment),
            capture_output=capture_output,
            text=capture_output,
        )

        collected: int | None = None
        executed: int | None = None
        metrics_exit_code: int | None = None
        metrics_error: str | None = None
        try:
            collected, executed, metrics_exit_code = _read_metrics(metrics_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            metrics_error = f"missing or invalid execution metrics: {exc}"

        failure_reason: str | None
        if completed.returncode != 0:
            failure_reason = f"pytest exited with status {completed.returncode}"
        elif metrics_error is not None:
            failure_reason = metrics_error
        elif metrics_exit_code != completed.returncode:
            failure_reason = (
                "pytest metrics exit code does not match the subprocess exit code"
            )
        elif collected is None or collected <= 0:
            failure_reason = "pytest selected zero tests"
        elif executed is None or executed <= 0:
            failure_reason = "pytest executed zero tests"
        else:
            failure_reason = None

        guarded_returncode = (
            0
            if failure_reason is None
            else completed.returncode or GUARD_FAILURE_EXIT_CODE
        )
        return PytestRunResult(
            command=command,
            pytest_returncode=completed.returncode,
            returncode=guarded_returncode,
            collected=collected,
            executed=executed,
            failure_reason=failure_reason,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


class _ExecutionMetricsPlugin:
    def __init__(self, metrics_path: Path) -> None:
        self._metrics_path = metrics_path
        self._collected = 0
        self._executed = 0

    def pytest_collection_finish(self, session: object) -> None:
        self._collected = len(session.items)  # type: ignore[attr-defined]

    def pytest_runtest_logreport(self, report: object) -> None:
        if report.when == "call":  # type: ignore[attr-defined]
            self._executed += 1

    def pytest_sessionfinish(self, session: object, exitstatus: object) -> None:
        del session
        _atomic_write_json(
            self._metrics_path,
            {
                "schemaVersion": METRICS_SCHEMA,
                "collected": self._collected,
                "executed": self._executed,
                "pytestExitCode": int(exitstatus),  # type: ignore[arg-type]
            },
        )


def _bootstrap_main(arguments: Sequence[str]) -> int:
    if len(arguments) < 3 or arguments[0] != _BOOTSTRAP_FLAG or arguments[2] != "--":
        print("invalid hermetic pytest bootstrap invocation", file=sys.stderr)
        return GUARD_FAILURE_EXIT_CODE

    metrics_path = Path(arguments[1]).resolve()
    pytest_arguments = list(arguments[3:])

    environment = hermetic_environment()
    os.environ.clear()
    os.environ.update(environment)

    # ``-I`` prevents PYTHONPATH and user-site injection at interpreter startup.
    # Retain only interpreter-owned stdlib/site paths, then add the repository
    # root explicitly for tests and application imports.
    trusted_prefixes = {
        Path(sys.base_prefix).resolve(),
        Path(sys.prefix).resolve(),
    }
    trusted_entries: list[str] = []
    for entry in sys.path:
        if not entry:
            continue
        resolved_entry = Path(entry).resolve()
        if any(
            resolved_entry == prefix or resolved_entry.is_relative_to(prefix)
            for prefix in trusted_prefixes
        ):
            trusted_entries.append(entry)

    root_text = str(ROOT)
    sys.path[:] = trusted_entries
    sys.path.insert(0, root_text)

    import pytest

    plugin = _ExecutionMetricsPlugin(metrics_path)
    return int(pytest.main(pytest_arguments, plugins=[plugin]))


def main(arguments: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if arguments and arguments[0] == _BOOTSTRAP_FLAG:
        return _bootstrap_main(arguments)

    result = run_pytest(arguments)
    print(result.summary(), flush=True)
    if result.failure_reason is not None:
        print(f"Hermetic pytest guard failed: {result.failure_reason}", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
