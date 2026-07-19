"""CI must preserve the repository's exact Rust and platform contract."""

from __future__ import annotations

import re
from pathlib import Path
import tomllib
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
WORKSPACE_MANIFEST_PATH = ROOT / "Cargo.toml"
RUST_TOOLCHAIN_PATH = ROOT / "rust-toolchain.toml"
EXPRESSION_CONTEXT = re.compile(r"\$\{\{\s*([A-Za-z_][A-Za-z0-9_-]*)[.\s]")
JOB_ENV_CONTEXTS = {
    "github",
    "needs",
    "strategy",
    "matrix",
    "vars",
    "secrets",
    "inputs",
}


def _workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in job["steps"] if step.get("name") == name)


def _required_rust_version() -> str:
    workspace = tomllib.loads(WORKSPACE_MANIFEST_PATH.read_text(encoding="utf-8"))
    toolchain = tomllib.loads(RUST_TOOLCHAIN_PATH.read_text(encoding="utf-8"))
    workspace_version = workspace["workspace"]["package"]["rust-version"]
    toolchain_version = toolchain["toolchain"]["channel"]
    assert workspace_version == toolchain_version
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", workspace_version)
    return workspace_version


def test_rust_ci_covers_exact_msrv_and_stable_on_both_platforms() -> None:
    required_rust_version = _required_rust_version()
    jobs = _workflow()["jobs"]
    rust = jobs["rust"]
    lanes = rust["strategy"]["matrix"]["include"]
    observed = {
        (lane["os"], lane["lane"], lane["toolchain"], lane["run_fmt"])
        for lane in lanes
    }
    assert observed == {
        ("ubuntu-24.04", "msrv", required_rust_version, True),
        ("windows-2025", "msrv", required_rust_version, True),
        ("ubuntu-24.04", "stable", "stable", False),
        ("windows-2025", "stable", "stable", False),
    }
    assert rust["env"]["RUSTUP_TOOLCHAIN"] == "${{ matrix.toolchain }}"
    assert "CARGO_TARGET_DIR" not in rust["env"]
    assert not any(
        str(step.get("uses", "")).startswith("actions/cache@")
        for step in rust["steps"]
    )

    commands = "\n".join(
        str(step.get("run", ""))
        for step in rust["steps"]
        if isinstance(step, dict)
    )
    for required_command in (
        "cargo fmt --all --check",
        "cargo test --workspace --locked",
        "cargo clippy --workspace --all-targets --locked -- -D warnings",
        "cargo build -p telysta-desktop --locked",
        "git diff --exit-code",
    ):
        assert required_command in commands

    exact_assertion = str(_step(rust, "Assert exact MSRV toolchain")["run"])
    assert "$actualRustc" in exact_assertion
    assert "$actualCargo" in exact_assertion
    assert exact_assertion.count(required_rust_version) >= 4

    linux_packages = str(
        _step(rust, "Install Linux Tauri prerequisites")["run"]
    )
    for package in (
        "libwebkit2gtk-4.1-dev",
        "build-essential",
        "curl",
        "wget",
        "file",
        "libxdo-dev",
        "libssl-dev",
        "libayatana-appindicator3-dev",
        "librsvg2-dev",
    ):
        assert package in linux_packages


def test_python_ci_uses_the_hermetic_runner_without_an_early_poetry_cache() -> None:
    jobs = _workflow()["jobs"]
    for step in jobs["python"]["steps"]:
        if step.get("uses") == "actions/setup-python@v6":
            assert "cache" not in step
    run_checks = _step(jobs["python"], "Run required checks")
    assert run_checks["run"] == "poetry run python -I scripts/check.py"


def test_job_level_environment_uses_only_server_available_contexts() -> None:
    for job_name, job in _workflow()["jobs"].items():
        for variable, value in job.get("env", {}).items():
            contexts = set(EXPRESSION_CONTEXT.findall(str(value)))
            assert contexts <= JOB_ENV_CONTEXTS, (
                f"job-level env {job_name}.{variable} uses unavailable "
                f"contexts: {sorted(contexts - JOB_ENV_CONTEXTS)}"
            )
