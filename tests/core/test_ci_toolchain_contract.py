"""Keep local toolchains exact and remote execution disabled.

The archived CI matrix is a historical reference, not an active verification
service or evidence of a platform run.
"""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path
from typing import Any

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility.
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / "docs" / "archive" / "ci-workflow-2026-10-16.yml"
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


def test_archived_rust_matrix_preserves_the_exact_platform_reference() -> None:
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


def test_archived_python_matrix_preserves_the_hermetic_runner_reference() -> None:
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


def test_repository_does_not_schedule_remote_execution() -> None:
    workflows = ROOT / ".github" / "workflows"
    active = [path for path in workflows.rglob("*") if path.suffix.lower() in {".yml", ".yaml"}]
    assert not active, f"Local-only verification forbids active GitHub workflows: {active}"


def test_desktop_icons_are_available_for_linux_and_windows() -> None:
    desktop = ROOT / "apps" / "desktop" / "src-tauri"
    config = json.loads((desktop / "tauri.conf.json").read_text(encoding="utf-8"))
    icons = config["bundle"]["icon"]
    assert {Path(name).suffix for name in icons} >= {".png", ".ico"}
    for name in icons:
        assert (desktop / name).is_file(), name
    png = (desktop / "icons" / "icon.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert png[12:16] == b"IHDR"
    width, height, depth, color_type = struct.unpack(">IIBB", png[16:26])
    assert width == height and width >= 32
    assert (depth, color_type) == (8, 6), "Tauri requires an RGBA icon"


def test_static_desktop_client_has_its_tauri_command_bridge() -> None:
    desktop = ROOT / "apps" / "desktop"
    config = json.loads(
        (desktop / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    )
    client = (desktop / "web" / "app.js").read_text(encoding="utf-8")
    assert "window.__TAURI__?.core?.invoke" in client
    assert config["app"].get("withGlobalTauri") is True
