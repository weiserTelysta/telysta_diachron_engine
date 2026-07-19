"""Run the repository's required local and CI quality checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __package__:
    from .pytest_runner import hermetic_environment, run_pytest
else:
    scripts_directory = str(Path(__file__).resolve().parent)
    if scripts_directory not in sys.path:
        sys.path.insert(0, scripts_directory)
    from pytest_runner import hermetic_environment, run_pytest


COMMANDS = (
    ("Compile", [sys.executable, "-I", "-m", "compileall", "-q", "app", "ui", "tests", "scripts", "main.py", "streamlit_app.py"]),
    ("Lint", [sys.executable, "-I", "-m", "ruff", "check", "app", "ui", "tests", "scripts", "main.py", "streamlit_app.py"]),
    ("Docs", [sys.executable, "-I", "scripts/docs_check.py"]),
)
TEST_ARGUMENTS = ("tests", "-q")


def main() -> int:
    child_environment = hermetic_environment()
    for label, command in COMMANDS:
        print(f"==> {label}", flush=True)
        completed = subprocess.run(
            command,
            check=False,
            env=child_environment,
        )
        if completed.returncode != 0:
            return completed.returncode

    print("==> Test", flush=True)
    test_result = run_pytest(TEST_ARGUMENTS)
    print(test_result.summary(), flush=True)
    if test_result.failure_reason is not None:
        print(
            f"Hermetic pytest guard failed: {test_result.failure_reason}",
            file=sys.stderr,
        )
    if test_result.returncode != 0:
        return test_result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
