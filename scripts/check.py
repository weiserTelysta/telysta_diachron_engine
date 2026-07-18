"""Run the repository's required local and CI quality checks."""

from __future__ import annotations

import subprocess
import sys


COMMANDS = (
    ("Compile", [sys.executable, "-m", "compileall", "-q", "app", "ui", "tests", "scripts", "main.py", "streamlit_app.py"]),
    ("Lint", [sys.executable, "-m", "ruff", "check", "app", "ui", "tests", "scripts", "main.py", "streamlit_app.py"]),
    ("Docs", [sys.executable, "scripts/docs_check.py"]),
    (
        "Test",
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "tests",
            "-q",
        ],
    ),
)


def main() -> int:
    for label, command in COMMANDS:
        print(f"==> {label}", flush=True)
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
