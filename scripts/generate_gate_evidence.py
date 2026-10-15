"""Generate reproducible G0A evidence and its derived human-readable status."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker
from packaging.markers import Marker, default_environment
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from referencing import Registry, Resource
import yaml

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 uses the locked stdlib backport.
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_PATH = Path("docs/G0A_GATE_EVIDENCE_2026-07-17.json")
DEFAULT_STATUS_PATH = Path("docs/STATUS.md")
GATE_EVIDENCE_SCHEMA_PATH = Path("docs/GATE_EVIDENCE_MANIFEST_V3.schema.json")
GATE_EVIDENCE_V2_SCHEMA_PATH = Path("docs/GATE_EVIDENCE_MANIFEST_V2.schema.json")
GATE_EVIDENCE_V1_SCHEMA_PATH = Path("docs/GATE_EVIDENCE_MANIFEST_V1.schema.json")
GATE_POLICY_PATH = Path("docs/G0A_POLICY_V2.json")
GATE_POLICY_SCHEMA_PATH = Path("docs/G0A_POLICY_V2.schema.json")
RUST_TOOLCHAIN_PATH = Path("rust-toolchain.toml")
VERIFIER_LEASE_PATH = Path(".git/telysta-g0a-verifier.lock")
GATE_EVIDENCE_SCHEMA_VERSION = "telysta-gate-evidence-manifest.v3"
GATE_POLICY_SCHEMA_VERSION = "telysta-g0a-policy.v2"
DELIVERY_READINESS_SCHEMA_VERSION = "telysta-delivery-readiness.v1"
FINGERPRINT_SCHEMA = "telysta-git-worktree-fingerprint.v2"
GENERATED_PATHS = (DEFAULT_EVIDENCE_PATH, DEFAULT_STATUS_PATH)


def _pinned_rust_version(root: Path) -> str:
    """Return the exact repository toolchain after validating its contract."""

    toolchain_path = root / RUST_TOOLCHAIN_PATH
    manifest = tomllib.loads(toolchain_path.read_text(encoding="utf-8"))
    toolchain = manifest.get("toolchain")
    if not isinstance(toolchain, dict):
        raise ValueError(f"{RUST_TOOLCHAIN_PATH} must define [toolchain]")
    channel = toolchain.get("channel")
    if not isinstance(channel, str):
        raise ValueError(f"{RUST_TOOLCHAIN_PATH} must define a string channel")
    try:
        parsed = Version(channel)
    except InvalidVersion as error:
        raise ValueError(f"{RUST_TOOLCHAIN_PATH} channel must be an exact Rust release") from error
    if parsed.is_prerelease or parsed.is_devrelease or len(parsed.release) != 3:
        raise ValueError(f"{RUST_TOOLCHAIN_PATH} channel must use an exact stable x.y.z release")
    if toolchain.get("profile") != "minimal":
        raise ValueError(f"{RUST_TOOLCHAIN_PATH} must use the minimal profile")
    components = toolchain.get("components")
    if not isinstance(components, list) or not {"rustfmt", "clippy"}.issubset(components):
        raise ValueError(f"{RUST_TOOLCHAIN_PATH} must install rustfmt and clippy")
    return channel


# This bootstrap value must remain import-safe. Reading a mutable workspace file
# here could terminate the process before generate() persists its fail-closed
# checkpoint. Contract tests bind it to Cargo.toml, rust-toolchain.toml, CI, and
# the verification command factories.
REQUIRED_RUST_VERSION = "1.88.0"
PYTHON_LOCK_GROUPS = frozenset({"main", "dev"})
ALLOWED_UNMANAGED_PYTHON_DISTRIBUTIONS = frozenset({"pip", "setuptools", "wheel"})
ADR_EXECUTABLE_CLAIM = "ADR-011 planning evidence is executable and ready for independent review"
PLATFORM_REVIEW_CLAIM = "R0A-03 platform and R0A-04 RNG compatibility evidence are ready for independent review"
RNG_VERIFIED_CLAIM = "the current Rust RNG behavior matches the recorded v1 known-answer vectors"
WORKTREE_VERIFICATION_CLAIM_SUFFIX = "worktree passes the recorded Python and Rust verification commands"
PYTHON_GATE_PROTOCOL = r".\.venv\Scripts\python.exe -I scripts\check.py"
CARGO_FMT_PROTOCOL = f"cargo +{REQUIRED_RUST_VERSION} fmt --all --check"
CARGO_TEST_PROTOCOL = f"cargo +{REQUIRED_RUST_VERSION} test --workspace --locked"
CARGO_CLIPPY_PROTOCOL = f"cargo +{REQUIRED_RUST_VERSION} clippy --workspace --all-targets --locked -- -D warnings"
CARGO_DESKTOP_BUILD_PROTOCOL = f"cargo +{REQUIRED_RUST_VERSION} build -p telysta-desktop --locked"
TARGETED_PYTHON_PROTOCOL = (
    r".\.venv\Scripts\python.exe -I scripts\pytest_runner.py "
    r"tests\core\test_adr_011_contract.py -q"
)
TARGETED_ADR_RUST_PROTOCOL = (
    f"cargo +{REQUIRED_RUST_VERSION} test -p telysta-core --test adr_011_schema_records --locked"
)
TARGETED_RNG_RUST_PROTOCOL = f"cargo +{REQUIRED_RUST_VERSION} test -p telysta-core --test rng_known_answers --locked"
NODE_PROTOCOL = "node --check apps/desktop/web/app.js"
GATE_REFRESH_PROTOCOL = "GateEvidence refresh validation"
GATE_POLICY_PROTOCOL = "GateEvidence passed-decision validation"
FINAL_DOCS_CHECK_PROTOCOL = "python -I scripts/docs_check.py (post-generation)"
VERIFICATION_FAILURE_BLOCKER_ID = "G0A-B98"
LOCK_FILES = (Path("Cargo.lock"), Path("poetry.lock"))
G0A_REQUIRED_REQUIREMENT_IDS = frozenset(
    {
        "R0A-01",
        "R0A-02-ADR011",
        "R0A-03",
        "R0A-04",
        "R0A-05",
        "R0A-06",
        "R0A-07",
        "R0A-08",
        "R0A-09",
        "R0A-10",
    }
)
G0A_REQUIRED_DELIVERY_WORK_PACKAGE_IDS = frozenset(
    {
        "R0A-01",
        "R0A-02",
        "R0A-03",
        "R0A-04",
        "R0A-05",
        "R0A-06",
        "R0A-07",
        "R0A-08",
        "R0A-09",
        "R0A-10",
        "R1-01",
        "R1-01A",
        "R1-02A",
        "R1-02B",
        "R1-02C",
        "R1-02D",
        "R1-02E",
        "R1-03",
        "R1-04",
        "R1-05",
        "R1-06",
        "R1-07",
        "R1-08",
        "R1-09",
        "R1-10",
    }
)
G0A_REQUIRED_EVIDENCE_KINDS = frozenset(
    {
        "SoftwareVerificationEvidence",
        "ArchitectureContractEvidence",
        "ArchitectureDecisionEvidence",
        "DeterminismEvidence",
    }
)
G0A_REQUIRED_PROTOCOL_ORDER = (
    PYTHON_GATE_PROTOCOL,
    TARGETED_PYTHON_PROTOCOL,
    CARGO_FMT_PROTOCOL,
    CARGO_TEST_PROTOCOL,
    TARGETED_ADR_RUST_PROTOCOL,
    TARGETED_RNG_RUST_PROTOCOL,
    CARGO_CLIPPY_PROTOCOL,
    CARGO_DESKTOP_BUILD_PROTOCOL,
    NODE_PROTOCOL,
)
G0A_REQUIRED_PROTOCOLS = frozenset(G0A_REQUIRED_PROTOCOL_ORDER)
PROTOCOL_PATHS = {
    PYTHON_GATE_PROTOCOL: "scripts/check.py",
    TARGETED_PYTHON_PROTOCOL: "tests/core/test_adr_011_contract.py",
    CARGO_FMT_PROTOCOL: "Cargo.toml",
    CARGO_TEST_PROTOCOL: "Cargo.toml",
    TARGETED_ADR_RUST_PROTOCOL: ("crates/telysta-core/tests/adr_011_schema_records.rs"),
    TARGETED_RNG_RUST_PROTOCOL: "crates/telysta-core/tests/rng_known_answers.rs",
    CARGO_CLIPPY_PROTOCOL: "Cargo.toml",
    CARGO_DESKTOP_BUILD_PROTOCOL: "apps/desktop/src-tauri/Cargo.toml",
    NODE_PROTOCOL: "apps/desktop/web/app.js",
}
VERIFICATION_ENVIRONMENT_FIELDS = frozenset(
    {
        "platform",
        "pythonExecutable",
        "pythonVersion",
        "pythonInstalledDistributionsSha256",
        "pythonLockStatus",
        "pythonLockMismatches",
        "rustcVersion",
        "cargoVersion",
        "requiredRustVersion",
        "rustVersionMeetsWorkspace",
        "nodeVersion",
        "lockFileSha256",
    }
)

VERIFICATION_COMMANDS = (
    (
        PYTHON_GATE_PROTOCOL,
        lambda root: [str(repository_python(root)), "-I", "scripts/check.py"],
        "required Python and documentation gate passed",
    ),
    (
        TARGETED_PYTHON_PROTOCOL,
        lambda root: [
            str(repository_python(root)),
            "-I",
            "scripts/pytest_runner.py",
            str(Path("tests") / "core" / "test_adr_011_contract.py"),
            "-q",
        ],
        "targeted ADR-011 Python contract passed through the hermetic runner",
    ),
    (
        CARGO_FMT_PROTOCOL,
        lambda root: [
            "cargo",
            f"+{REQUIRED_RUST_VERSION}",
            "fmt",
            "--all",
            "--check",
        ],
        "no formatting differences",
    ),
    (
        CARGO_TEST_PROTOCOL,
        lambda root: [
            "cargo",
            f"+{REQUIRED_RUST_VERSION}",
            "test",
            "--workspace",
            "--locked",
        ],
        "Rust workspace tests passed",
    ),
    (
        TARGETED_ADR_RUST_PROTOCOL,
        lambda root: [
            "cargo",
            f"+{REQUIRED_RUST_VERSION}",
            "test",
            "-p",
            "telysta-core",
            "--test",
            "adr_011_schema_records",
            "--locked",
        ],
        "targeted ADR-011 Rust contract passed directly",
    ),
    (
        TARGETED_RNG_RUST_PROTOCOL,
        lambda root: [
            "cargo",
            f"+{REQUIRED_RUST_VERSION}",
            "test",
            "-p",
            "telysta-core",
            "--test",
            "rng_known_answers",
            "--locked",
        ],
        "targeted Rust RNG known answers passed directly",
    ),
    (
        CARGO_CLIPPY_PROTOCOL,
        lambda root: [
            "cargo",
            f"+{REQUIRED_RUST_VERSION}",
            "clippy",
            "--workspace",
            "--all-targets",
            "--locked",
            "--",
            "-D",
            "warnings",
        ],
        "zero warnings",
    ),
    (
        CARGO_DESKTOP_BUILD_PROTOCOL,
        lambda root: [
            "cargo",
            f"+{REQUIRED_RUST_VERSION}",
            "build",
            "-p",
            "telysta-desktop",
            "--locked",
        ],
        "desktop application compiled with the exact workspace MSRV",
    ),
    (
        NODE_PROTOCOL,
        lambda root: ["node", "--check", "apps/desktop/web/app.js"],
        "desktop JavaScript syntax passed",
    ),
)


@dataclass(frozen=True)
class WorkspaceFingerprint:
    base_commit: str
    dirty: bool
    status_entry_count: int
    sha256: str


class VerifierLeaseError(RuntimeError):
    """Raised when another verifier owns the repository publication lease."""


def repository_python(root: Path) -> Path:
    """Return the repository-managed Python interpreter for this platform."""

    candidates = (
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            # Resolving the final symlink on Unix launches the base interpreter
            # without pyvenv.cfg, losing this environment's installed packages.
            return candidate.parent.resolve() / candidate.name
    raise FileNotFoundError("repository Python environment is missing; create .venv before verification")


def _validate_repository_python(root: Path) -> Path:
    expected = repository_python(root)
    actual = Path(sys.executable).absolute()
    prefix = Path(sys.prefix).resolve()
    if (actual.resolve() != expected.resolve()
            or prefix != (root / ".venv").resolve()
            or prefix == Path(sys.base_prefix).resolve()):
        raise RuntimeError(
            f"gate verification must run from the repository interpreter: "
            f"expected {expected}, got {actual} with prefix {prefix}"
        )
    return actual


def _validated_verified_at(value: str) -> str:
    candidate = value.strip()
    try:
        moment = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("verifiedAt must be an ISO UTC date-time") from error
    if not candidate.endswith("Z") or moment.tzinfo is None:
        raise ValueError("verifiedAt must be an ISO UTC date-time ending in Z")
    return candidate


def _iso_moment(value: str) -> datetime:
    if "T" in value:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            return moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc)
    return datetime.combine(date.fromisoformat(value), time.min, tzinfo=timezone.utc)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _platform_family(value: str | None = None) -> str:
    candidate = (value or sys.platform or "").casefold()
    if candidate.startswith("win") or "windows" in candidate:
        return "windows"
    if candidate.startswith("linux") or "linux" in candidate:
        return "linux"
    if candidate.startswith("darwin") or "macos" in candidate or "mac os" in candidate:
        return "macos"
    return "other"


def _evidence_id(
    *,
    kind: str,
    path: str,
    protocol: str | None = None,
) -> str:
    identity = "\0".join((kind, path, protocol or "")).encode("utf-8")
    return "evidence:" + hashlib.sha256(identity).hexdigest()[:32]


def _normalise_evidence_item_v3(item: dict[str, Any]) -> dict[str, Any]:
    kind = str(item.get("kind", "ArchitectureContractEvidence"))
    path = str(item.get("path", ""))
    protocol = item.get("protocol")
    if kind == "ArchitectureContractEvidence" and path == (
        "docs/adr/ADR-011-project-manifest-run-ledger-job-identity.md"
    ):
        kind = "ArchitectureDecisionEvidence"
    result_map = {
        "not_run_for_fingerprint": "pending",
        "draft_2020_12_validated": "pass",
        "proposed": "pending",
        "proposed_ready_for_independent_review": "pending",
        "ready_for_independent_review": "pending",
        "self_review_complete": "pending",
    }
    result = result_map.get(str(item.get("result", "pending")), item.get("result"))
    if result not in {
        "pending",
        "pass",
        "fail",
        "accepted",
        "rejected",
        "accepted_terminal",
    }:
        result = "pending"
    normalised: dict[str, Any] = {
        "evidenceId": str(
            item.get("evidenceId")
            or _evidence_id(
                kind=kind,
                path=path,
                protocol=protocol if isinstance(protocol, str) else None,
            )
        ),
        "kind": kind,
        "path": path,
        "sha256": item.get("sha256", "0" * 64),
        "result": result,
    }
    for field in (
        "protocol",
        "details",
        "verificationMode",
        "executedCommand",
        "coveredBy",
        "remoteProvenance",
    ):
        if field in item:
            normalised[field] = copy.deepcopy(item[field])
    return normalised


def _normalise_environment_v3(environment: dict[str, Any]) -> dict[str, Any]:
    toolchain = environment.get("toolchain")
    if not isinstance(toolchain, dict):
        toolchain = {
            "python": str(environment.get("pythonVersion", "unavailable")),
            "rustc": str(environment.get("rustcVersion", "unavailable")),
            "cargo": str(environment.get("cargoVersion", "unavailable")),
            "node": str(environment.get("nodeVersion", "unavailable")),
        }
    return {
        "os": str(environment.get("os") or environment.get("platform") or "unavailable"),
        "architecture": str(environment.get("architecture") or platform.machine() or "unavailable"),
        "toolchain": {
            "python": str(toolchain.get("python", "unavailable")),
            "rustc": str(toolchain.get("rustc", "unavailable")),
            "cargo": str(toolchain.get("cargo", "unavailable")),
            "node": str(toolchain.get("node", "unavailable")),
        },
        "lockFileSha256": copy.deepcopy(environment.get("lockFileSha256", {})),
    }


def _normalise_verification_run_v3(run: dict[str, Any]) -> dict[str, Any] | None:
    environment = run.get("environment")
    if not isinstance(environment, dict):
        return None
    subject_commit = run.get("subjectCommit")
    subject_tree = run.get("subjectTree")
    if not isinstance(subject_commit, str) or not isinstance(subject_tree, str):
        return None
    return {
        "runId": str(run.get("runId", "")),
        "subjectCommit": subject_commit,
        "subjectTree": subject_tree,
        "platformFamily": str(
            run.get("platformFamily") or _platform_family(str(environment.get("os") or environment.get("platform")))
        ),
        "startedAt": str(run.get("startedAt", "")),
        "finishedAt": str(run.get("finishedAt", "")),
        "result": "pass" if run.get("result") == "pass" else "fail",
        "protocols": list(dict.fromkeys(run.get("protocols", []))),
        "environment": _normalise_environment_v3(environment),
        "remoteProvenance": copy.deepcopy(run.get("remoteProvenance")),
    }


def _schema_errors(
    evidence: dict[str, Any],
    *,
    root: Path = ROOT,
) -> list[str]:
    schema = json.loads((root / GATE_EVIDENCE_SCHEMA_PATH).read_text(encoding="utf-8"))
    v2_schema = json.loads((root / GATE_EVIDENCE_V2_SCHEMA_PATH).read_text(encoding="utf-8"))
    v1_schema = json.loads((root / GATE_EVIDENCE_V1_SCHEMA_PATH).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator.check_schema(v2_schema)
    Draft202012Validator.check_schema(v1_schema)
    registry = (
        Registry()
        .with_resource(
            v1_schema["$id"],
            Resource.from_contents(v1_schema),
        )
        .with_resource(
            v2_schema["$id"],
            Resource.from_contents(v2_schema),
        )
    )
    validator = Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors: list[str] = []
    for error in sorted(
        validator.iter_errors(evidence),
        key=lambda item: ".".join(str(part) for part in item.absolute_path),
    ):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


def _policy_contract_issues(
    evidence: dict[str, Any],
    *,
    root: Path,
) -> list[str]:
    """Validate policy identity and closed predicate vocabulary for every decision."""

    try:
        policy_schema = json.loads((root / GATE_POLICY_SCHEMA_PATH).read_text(encoding="utf-8"))
        policy_payload = (root / GATE_POLICY_PATH).read_bytes()
        policy = json.loads(policy_payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return [f"G0A policy bootstrap failed: {type(error).__name__}: {error}"]

    issues: list[str] = []
    try:
        Draft202012Validator.check_schema(policy_schema)
    except Exception as error:  # noqa: BLE001 - report schema bootstrap failures.
        return [f"G0A policy schema is invalid: {type(error).__name__}: {error}"]
    validator = Draft202012Validator(
        policy_schema,
        format_checker=FormatChecker(),
    )
    for error in sorted(
        validator.iter_errors(policy),
        key=lambda item: ".".join(str(part) for part in item.absolute_path),
    ):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        issues.append(f"G0A policy {location}: {error.message}")

    if policy.get("schemaVersion") != GATE_POLICY_SCHEMA_VERSION:
        issues.append("G0A policy schemaVersion is not the required v2 contract")
    if policy.get("gateId") != "G0A":
        issues.append("G0A policy gateId differs from G0A")
    policy_requirement_ids = set(policy.get("requirements", {}))
    if policy_requirement_ids != G0A_REQUIRED_REQUIREMENT_IDS:
        issues.append(
            "G0A policy requirement IDs differ from the contract; "
            f"missing={sorted(G0A_REQUIRED_REQUIREMENT_IDS - policy_requirement_ids)}; "
            f"unexpected={sorted(policy_requirement_ids - G0A_REQUIRED_REQUIREMENT_IDS)}"
        )
    policy_work_packages = set(policy.get("requiredWorkPackageIds", []))
    if policy_work_packages != G0A_REQUIRED_DELIVERY_WORK_PACKAGE_IDS:
        issues.append(
            "G0A policy delivery work-package IDs differ from the contract; "
            f"missing={sorted(G0A_REQUIRED_DELIVERY_WORK_PACKAGE_IDS - policy_work_packages)}; "
            f"unexpected={sorted(policy_work_packages - G0A_REQUIRED_DELIVERY_WORK_PACKAGE_IDS)}"
        )

    reference = evidence.get("gatePolicy")
    expected_sha = hashlib.sha256(policy_payload).hexdigest()
    if not isinstance(reference, dict):
        issues.append("GateEvidence gatePolicy reference is missing")
    else:
        expected_reference = {
            "path": GATE_POLICY_PATH.as_posix(),
            "schemaVersion": GATE_POLICY_SCHEMA_VERSION,
            "sha256": expected_sha,
        }
        for field, expected in expected_reference.items():
            if reference.get(field) != expected:
                issues.append(f"GateEvidence gatePolicy {field} differs from policy v2")
    return issues


def validate_gate_evidence_manifest(
    evidence: dict[str, Any],
    *,
    root: Path = ROOT,
    now: datetime | None = None,
) -> None:
    """Validate the closed G0A manifest contract before interpreting a decision."""

    issues = _schema_errors(evidence, root=root)
    issues.extend(_policy_contract_issues(evidence, root=root))

    requirements = evidence.get("requirements")
    if isinstance(requirements, list):
        requirement_ids = [item.get("id") for item in requirements if isinstance(item, dict)]
        if len(requirement_ids) != len(set(requirement_ids)):
            issues.append("requirements contain duplicate IDs")
        if set(requirement_ids) != G0A_REQUIRED_REQUIREMENT_IDS:
            missing = sorted(G0A_REQUIRED_REQUIREMENT_IDS - set(requirement_ids))
            unexpected = sorted(set(requirement_ids) - G0A_REQUIRED_REQUIREMENT_IDS)
            issues.append(f"G0A requirement IDs differ from the contract; missing={missing}; unexpected={unexpected}")

    evidence_items = evidence.get("evidence")
    if isinstance(evidence_items, list):
        evidence_ids = [item.get("evidenceId") for item in evidence_items if isinstance(item, dict)]
        if len(evidence_ids) != len(set(evidence_ids)):
            issues.append("evidence contains duplicate evidenceId values")
        known_evidence_ids = {evidence_id for evidence_id in evidence_ids if isinstance(evidence_id, str)}
        kinds = {item.get("kind") for item in evidence_items if isinstance(item, dict)}
        missing_kinds = sorted(G0A_REQUIRED_EVIDENCE_KINDS - kinds)
        if missing_kinds:
            issues.append("G0A evidence kinds are missing: " + ", ".join(missing_kinds))
        protocols = [
            item.get("protocol")
            for item in evidence_items
            if isinstance(item, dict)
            and item.get("kind") == "SoftwareVerificationEvidence"
            and isinstance(item.get("protocol"), str)
        ]
        if len(protocols) != len(set(protocols)):
            issues.append("software evidence contains duplicate protocols")
        protocol_set = {protocol for protocol in protocols if isinstance(protocol, str)}
        if protocol_set != G0A_REQUIRED_PROTOCOLS:
            missing = sorted(G0A_REQUIRED_PROTOCOLS - protocol_set)
            unexpected = sorted(protocol_set - G0A_REQUIRED_PROTOCOLS)
            issues.append(
                f"G0A verification protocols differ from the contract; missing={missing}; unexpected={unexpected}"
            )
        if isinstance(requirements, list):
            for requirement in requirements:
                if not isinstance(requirement, dict):
                    continue
                unresolved = sorted(
                    reference
                    for reference in requirement.get("evidenceRefs", [])
                    if reference not in known_evidence_ids
                )
                if unresolved:
                    issues.append(f"{requirement.get('id')} has unresolved evidenceRefs: {unresolved}")

    source = evidence.get("source")
    if isinstance(source, dict):
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)
        for run in source.get("verificationRuns", []):
            if not isinstance(run, dict):
                continue
            started_at = run.get("startedAt")
            finished_at = run.get("finishedAt")
            if not isinstance(started_at, str) or not isinstance(finished_at, str):
                continue
            try:
                _validated_verified_at(started_at)
                _validated_verified_at(finished_at)
                started = _iso_moment(started_at)
                finished = _iso_moment(finished_at)
            except ValueError as error:
                issues.append(str(error))
                continue
            if finished < started:
                issues.append(f"verification run finishes before it starts: {run.get('runId')}")
            if finished > current + timedelta(minutes=5):
                issues.append(f"verification run finishes in the future: {run.get('runId')}")
            if run.get("subjectCommit") != source.get("subjectCommit"):
                issues.append(f"verification run subject commit differs: {run.get('runId')}")
            if run.get("subjectTree") != source.get("subjectTree"):
                issues.append(f"verification run subject tree differs: {run.get('runId')}")

    if issues:
        raise ValueError("GateEvidence manifest is invalid: " + "; ".join(issues))


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def _exclude_pathspecs(excluded_paths: tuple[Path, ...]) -> list[str]:
    return [f":(exclude){path.as_posix()}" for path in excluded_paths]


def _commit_tree(root: Path, commit: str) -> str:
    return _git(root, "rev-parse", f"{commit}^{{tree}}").decode("ascii").strip()


def _subject_blob(root: Path, commit: str, relative: str) -> bytes:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"subject evidence path is unsafe: {relative}")
    return _git(root, "show", f"{commit}:{path.as_posix()}")


def _subject_content_issues(
    evidence: dict[str, Any],
    *,
    root: Path,
) -> list[str]:
    source = evidence.get("source", {})
    subject = source.get("subjectCommit")
    if not isinstance(subject, str):
        return ["subject commit metadata is missing"]

    issues: list[str] = []
    expected_generated = [path.as_posix() for path in GENERATED_PATHS]
    if source.get("excludedGeneratedPaths") != expected_generated:
        issues.append("excludedGeneratedPaths differs from the generated-path contract")

    for item in evidence.get("evidence", []):
        if not isinstance(item, dict) or "sha256" not in item:
            continue
        relative = item.get("path")
        if not isinstance(relative, str) or not relative:
            issues.append("hashed evidence path is missing")
            continue
        try:
            payload = _subject_blob(root, subject, relative)
        except (subprocess.CalledProcessError, ValueError):
            issues.append(f"hashed evidence is unavailable in subject: {relative}")
            continue
        actual = hashlib.sha256(payload).hexdigest()
        if item.get("sha256") != actual:
            issues.append(f"hashed evidence differs from subject: {relative}")

    policy_reference = evidence.get("gatePolicy")
    if isinstance(policy_reference, dict):
        relative = policy_reference.get("path")
        if isinstance(relative, str):
            try:
                payload = _subject_blob(root, subject, relative)
            except (subprocess.CalledProcessError, ValueError):
                issues.append(f"gate policy is unavailable in subject: {relative}")
            else:
                actual = hashlib.sha256(payload).hexdigest()
                if policy_reference.get("sha256") != actual:
                    issues.append("gate policy hash differs from subject")

    expected_lock_paths = {path.as_posix() for path in LOCK_FILES}
    subject_lock_hashes: dict[str, str] = {}
    for relative in expected_lock_paths:
        try:
            payload = _subject_blob(root, subject, relative)
        except (subprocess.CalledProcessError, ValueError):
            issues.append(f"lock file is unavailable in subject: {relative}")
            continue
        subject_lock_hashes[relative] = hashlib.sha256(payload).hexdigest()

    passing_runs = [
        run for run in source.get("verificationRuns", []) if isinstance(run, dict) and run.get("result") == "pass"
    ]
    for run in passing_runs:
        recorded = run.get("environment", {}).get("lockFileSha256")
        if recorded != subject_lock_hashes:
            issues.append(f"verification lock-file hashes differ from subject: {run.get('runId')}")
    return issues


def fingerprint_workspace(
    root: Path = ROOT,
    excluded_paths: tuple[Path, ...] = GENERATED_PATHS,
) -> WorkspaceFingerprint:
    """Hash tracked changes and every untracked file, excluding generated outputs."""

    exclusions = _exclude_pathspecs(excluded_paths)
    base_commit = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    diff = _git(root, "diff", "--binary", "HEAD", "--", ".", *exclusions)
    untracked_raw = _git(
        root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
        ".",
        *exclusions,
    )
    untracked = sorted(path.decode("utf-8", errors="surrogateescape") for path in untracked_raw.split(b"\0") if path)
    status = _git(
        root,
        "status",
        "--short",
        "--untracked-files=all",
        "--",
        ".",
        *exclusions,
    ).decode("utf-8", errors="surrogateescape")

    digest = hashlib.sha256()
    digest.update(FINGERPRINT_SCHEMA.encode("ascii"))
    digest.update(b"\0diff\0")
    digest.update(len(diff).to_bytes(8, "big"))
    digest.update(diff)
    for relative in untracked:
        path = root / relative
        relative_bytes = relative.encode("utf-8", errors="surrogateescape")
        digest.update(b"\0untracked\0")
        digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        if path.is_symlink():
            payload = os.readlink(path).encode("utf-8", errors="surrogateescape")
        else:
            payload = path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)

    return WorkspaceFingerprint(
        base_commit=base_commit,
        dirty=bool(diff or untracked),
        status_entry_count=len(status.splitlines()),
        sha256=digest.hexdigest(),
    )


def _refresh_hashed_evidence(root: Path, evidence: dict[str, Any]) -> None:
    for item in evidence.get("evidence", []):
        if "sha256" not in item:
            continue
        path = root / item["path"]
        if not path.is_file():
            raise FileNotFoundError(f"evidence path does not exist: {item['path']}")
        item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def _software_item(evidence: dict[str, Any], protocol: str) -> dict[str, Any]:
    for item in evidence["evidence"]:
        if item.get("protocol") == protocol:
            return item
    path = PROTOCOL_PATHS.get(protocol)
    if path is not None:
        item = {
            "evidenceId": _evidence_id(
                kind="SoftwareVerificationEvidence",
                path=path,
                protocol=protocol,
            ),
            "kind": "SoftwareVerificationEvidence",
            "path": path,
            "sha256": "0" * 64,
            "protocol": protocol,
            "result": "pending",
            "details": "not yet verified",
            "verificationMode": "not_run",
        }
        evidence["evidence"].append(item)
        return item
    raise KeyError(f"GateEvidence has no software item for protocol: {protocol}")


def _synchronize_required_software_items(evidence: dict[str, Any]) -> None:
    items = evidence.get("evidence", [])
    evidence["evidence"] = [
        item
        for item in items
        if not isinstance(item, dict)
        or item.get("kind") != "SoftwareVerificationEvidence"
        or not isinstance(item.get("protocol"), str)
        or item.get("protocol") in G0A_REQUIRED_PROTOCOLS
    ]
    for protocol in G0A_REQUIRED_PROTOCOL_ORDER:
        _software_item(evidence, protocol)


def _mark_software_stale(evidence: dict[str, Any]) -> None:
    for item in evidence.get("evidence", []):
        if item.get("kind") != "SoftwareVerificationEvidence" or not isinstance(item.get("protocol"), str):
            continue
        item["result"] = "pending"
        item["details"] = "verification must be rerun for the recorded worktree fingerprint"
        item["verificationMode"] = "not_run"
        item.pop("coveredBy", None)
        item.pop("executedCommand", None)


def _set_verification_blocker(evidence: dict[str, Any], summary: str) -> None:
    blockers = evidence.setdefault("blockers", [])
    blocker = next(
        (item for item in blockers if isinstance(item, dict) and item.get("id") == VERIFICATION_FAILURE_BLOCKER_ID),
        None,
    )
    if blocker is None:
        blockers.append(
            {
                "severity": "blocking",
                "id": VERIFICATION_FAILURE_BLOCKER_ID,
                "summary": summary,
            }
        )
        return
    blocker["severity"] = "blocking"
    blocker["summary"] = summary


def _clear_verification_blocker(evidence: dict[str, Any]) -> None:
    blockers = evidence.get("blockers")
    if not isinstance(blockers, list):
        return
    blockers[:] = [
        item for item in blockers if not isinstance(item, dict) or item.get("id") != VERIFICATION_FAILURE_BLOCKER_ID
    ]


def _set_gate_blocked(
    evidence: dict[str, Any],
    *,
    reason: str,
    invalidate_software: bool,
) -> None:
    """Invalidate a decision without creating a v3 pass claim."""

    evidence["decision"] = "blocked"
    evidence["decisionDate"] = _utc_timestamp()[:10]
    claims = evidence.setdefault("claims", {})
    allowed = claims.setdefault("allowed", [])
    forbidden = claims.setdefault("forbidden", [])
    allowed[:] = [claim for claim in allowed if claim != "G0A has passed"]
    if "G0A has passed" not in forbidden:
        forbidden.append("G0A has passed")
    if invalidate_software:
        _mark_software_stale(evidence)
        source = evidence.get("source")
        dirty = bool(source.get("worktreeDirty", True)) if isinstance(source, dict) else True
        _set_verified_worktree_claims(
            evidence,
            verified=False,
            dirty=dirty,
        )
    _set_verification_blocker(evidence, reason)


def _restore_requested_pass(evidence: dict[str, Any]) -> None:
    evidence["decision"] = "passed"
    claims = evidence.setdefault("claims", {})
    allowed = claims.setdefault("allowed", [])
    forbidden = claims.setdefault("forbidden", [])
    if "G0A has passed" not in allowed:
        allowed.append("G0A has passed")
    forbidden[:] = [claim for claim in forbidden if claim != "G0A has passed"]
    _clear_verification_blocker(evidence)


def _worktree_verification_claim(*, dirty: bool) -> str:
    state = "dirty" if dirty else "clean"
    return f"the recorded {state} {WORKTREE_VERIFICATION_CLAIM_SUFFIX}"


def _set_verified_worktree_claims(
    evidence: dict[str, Any],
    *,
    verified: bool,
    dirty: bool,
) -> None:
    allowed = evidence["claims"]["allowed"]
    allowed[:] = [
        claim
        for claim in allowed
        if claim not in {ADR_EXECUTABLE_CLAIM, PLATFORM_REVIEW_CLAIM, RNG_VERIFIED_CLAIM}
        and not claim.endswith(WORKTREE_VERIFICATION_CLAIM_SUFFIX)
    ]
    if verified:
        allowed.extend(
            (
                ADR_EXECUTABLE_CLAIM,
                PLATFORM_REVIEW_CLAIM,
                RNG_VERIFIED_CLAIM,
                _worktree_verification_claim(dirty=dirty),
            )
        )


def _refresh_clean_checkout_requirement(
    evidence: dict[str, Any],
    fingerprint: WorkspaceFingerprint,
) -> None:
    requirement = next(item for item in evidence["requirements"] if item["id"] == "R0A-05")
    if fingerprint.dirty:
        requirement["status"] = "failed"
        requirement["reason"] = (
            "the generated-evidence inputs contain "
            f"{fingerprint.status_entry_count} modified or untracked entries; "
            "HEAD does not contain the reviewed Rust/Tauri/doc baseline"
        )
    elif (
        requirement.get("status") == "passed"
        and isinstance(requirement.get("terminalEvidence"), dict)
        and requirement["terminalEvidence"].get("result") == "accepted_terminal"
    ):
        requirement.pop("reason", None)
    else:
        requirement["status"] = "ready_for_independent_review"
        requirement["reason"] = "the worktree is clean; independent clean-checkout reproduction is still required"


def _synchronise_terminal_blockers(evidence: dict[str, Any]) -> None:
    terminal_blockers = {
        "R0A-05": (
            "G0A-B02",
            "clean-checkout repository baseline terminal evidence is absent",
        ),
        "R0A-07": (
            "G0A-B04",
            "complete delivery readiness and independent approval are absent",
        ),
        "R0A-08": (
            "G0A-B05",
            "verification trust terminal evidence and Windows/Linux provenance are absent",
        ),
        "R0A-09": (
            "G0A-B06",
            "current v1 authority fault-matrix terminal evidence is absent",
        ),
        "R0A-10": (
            "G0A-B07",
            "legacy containment terminal evidence is absent",
        ),
    }
    requirements = {item.get("id"): item for item in evidence.get("requirements", []) if isinstance(item, dict)}
    blockers = [item for item in evidence.get("blockers", []) if isinstance(item, dict)]
    derived_ids = {blocker_id for blocker_id, _ in terminal_blockers.values()}
    blockers = [item for item in blockers if item.get("id") not in derived_ids]
    for requirement_id, (blocker_id, summary) in terminal_blockers.items():
        requirement = requirements.get(requirement_id, {})
        terminal = requirement.get("terminalEvidence")
        if (
            requirement.get("status") == "passed"
            and isinstance(terminal, dict)
            and terminal.get("result") == "accepted_terminal"
        ):
            continue
        blockers.append(
            {
                "severity": "blocking",
                "id": blocker_id,
                "summary": summary,
            }
        )
    for blocker in blockers:
        if blocker.get("id") == "G0A-B97":
            blocker["summary"] = (
                "the v2-to-v3 migration candidate requires independent review under GateEvidence v3 and G0A policy v2"
            )
    evidence["blockers"] = blockers


def _ensure_hashed_contract_evidence(
    evidence: dict[str, Any],
    *,
    path: Path,
    result: str,
) -> None:
    items = evidence.setdefault("evidence", [])
    existing = next(
        (
            item
            for item in items
            if isinstance(item, dict)
            and item.get("kind") == "ArchitectureContractEvidence"
            and item.get("path") == path.as_posix()
        ),
        None,
    )
    if existing is None:
        items.append(
            {
                "evidenceId": _evidence_id(
                    kind="ArchitectureContractEvidence",
                    path=path.as_posix(),
                ),
                "kind": "ArchitectureContractEvidence",
                "path": path.as_posix(),
                "sha256": "0" * 64,
                "result": result,
            }
        )
        return
    if existing.get("result") not in {"accepted", "accepted_terminal"}:
        existing["result"] = result
    existing.setdefault(
        "evidenceId",
        _evidence_id(
            kind="ArchitectureContractEvidence",
            path=path.as_posix(),
        ),
    )
    existing.setdefault("sha256", "0" * 64)


def _synchronize_gate_contract_inputs(
    root: Path,
    evidence: dict[str, Any],
) -> None:
    policy_payload = (root / GATE_POLICY_PATH).read_bytes()
    evidence["gatePolicy"] = {
        "path": GATE_POLICY_PATH.as_posix(),
        "schemaVersion": GATE_POLICY_SCHEMA_VERSION,
        "sha256": hashlib.sha256(policy_payload).hexdigest(),
    }
    for path, result in (
        (GATE_EVIDENCE_SCHEMA_PATH, "pass"),
        (GATE_POLICY_SCHEMA_PATH, "pass"),
        (GATE_POLICY_PATH, "pending"),
        (Path("docs/governance/GATE_EVIDENCE_MODEL_V3.md"), "pending"),
    ):
        _ensure_hashed_contract_evidence(evidence, path=path, result=result)


def _migrate_manifest_v3(
    root: Path,
    evidence: dict[str, Any],
) -> bool:
    """Migrate v1/v2 conservatively; old decisions and reviews never carry over."""

    if evidence.get("schemaVersion") == GATE_EVIDENCE_SCHEMA_VERSION:
        return False
    previous_version = str(evidence.get("schemaVersion", "unknown"))
    was_passed = evidence.get("decision") == "passed"
    evidence["$schema"] = GATE_EVIDENCE_SCHEMA_PATH.name
    evidence["schemaVersion"] = GATE_EVIDENCE_SCHEMA_VERSION
    evidence["decision"] = "blocked"
    evidence["reviewers"] = []
    evidence["waivers"] = []
    evidence["deliveryReadiness"] = {
        "schemaVersion": DELIVERY_READINESS_SCHEMA_VERSION,
        "workPackages": [],
    }
    evidence["evidence"] = [
        _normalise_evidence_item_v3(item) for item in evidence.get("evidence", []) if isinstance(item, dict)
    ]
    _synchronize_gate_contract_inputs(root, evidence)
    allowed = evidence.setdefault("claims", {}).setdefault("allowed", [])
    forbidden = evidence["claims"].setdefault("forbidden", [])
    if "G0A has passed" in allowed:
        allowed.remove("G0A has passed")
    if "G0A has passed" not in forbidden:
        forbidden.append("G0A has passed")
    blockers = evidence.setdefault("blockers", [])
    if not any(isinstance(item, dict) and item.get("id") == "G0A-B97" for item in blockers):
        blockers.append(
            {
                "severity": "blocking",
                "id": "G0A-B97",
                "summary": (
                    f"{previous_version} evidence must be re-evaluated under GateEvidence v3 and G0A policy v2"
                ),
            }
        )
    if was_passed and not any(isinstance(item, dict) and item.get("id") == "G0A-B99" for item in blockers):
        evidence.setdefault("blockers", []).append(
            {
                "severity": "blocking",
                "id": "G0A-B99",
                "summary": "legacy passed evidence must be independently re-verified under v3",
            }
        )
    existing_requirements = {
        item.get("id"): item for item in evidence.get("requirements", []) if isinstance(item, dict)
    }
    new_requirements = {
        "R0A-08": (
            "verification trust, cross-platform provenance and verifier lease",
            "hermetic local candidates exist, but independent review, verifier lease and trusted Windows/Linux fresh-checkout provenance are incomplete",
        ),
        "R0A-09": (
            "current v1 authority repair",
            "create-if-absent, append-only extension, migration archive and as-of projection fault evidence are incomplete",
        ),
        "R0A-10": (
            "legacy evidence containment",
            "raw legacy bytes, manifests and exact failure fingerprints are not frozen under independent review",
        ),
    }
    for requirement_id, (name, reason) in new_requirements.items():
        existing_requirements.setdefault(
            requirement_id,
            {
                "id": requirement_id,
                "name": name,
                "status": "incomplete",
                "evidenceRefs": [],
                "terminalEvidence": None,
                "reason": reason,
            },
        )
    evidence_by_path: dict[str, list[dict[str, Any]]] = {}
    for item in evidence["evidence"]:
        evidence_by_path.setdefault(str(item.get("path")), []).append(item)
    policy = json.loads((root / GATE_POLICY_PATH).read_text(encoding="utf-8"))
    for requirement_id, requirement in existing_requirements.items():
        old_paths = requirement.pop("evidencePaths", [])
        refs = [reference for reference in requirement.get("evidenceRefs", []) if isinstance(reference, str)]
        for relative in old_paths if isinstance(old_paths, list) else []:
            for item in evidence_by_path.get(str(relative), []):
                evidence_id = item.get("evidenceId")
                if isinstance(evidence_id, str) and evidence_id not in refs:
                    refs.append(evidence_id)
        requirement["evidenceRefs"] = refs
        terminal_rule = policy.get("requirements", {}).get(requirement_id, {}).get("terminalAcceptance")
        if isinstance(terminal_rule, dict):
            terminal_path = str(terminal_rule["evidencePath"])
            terminal_kind = str(terminal_rule["kind"])
            matching = next(
                (item for item in evidence_by_path.get(terminal_path, []) if item.get("kind") == terminal_kind),
                None,
            )
            if matching is None:
                requirement["terminalEvidence"] = {
                    "evidenceId": _evidence_id(
                        kind=terminal_kind,
                        path=terminal_path,
                    ),
                    "path": terminal_path,
                    "kind": terminal_kind,
                    "result": "pending",
                    "sha256": None,
                }
            else:
                evidence_id = str(matching["evidenceId"])
                if evidence_id not in refs:
                    refs.append(evidence_id)
                terminal: dict[str, Any] = {
                    "evidenceId": evidence_id,
                    "path": terminal_path,
                    "kind": terminal_kind,
                    "result": ("accepted_terminal" if matching.get("result") == "accepted_terminal" else "pending"),
                    "sha256": matching.get("sha256"),
                }
                if "remoteProvenance" in matching:
                    terminal["remoteProvenance"] = copy.deepcopy(matching["remoteProvenance"])
                requirement["terminalEvidence"] = terminal
        else:
            requirement["terminalEvidence"] = None
    evidence["requirements"] = [
        existing_requirements[requirement_id] for requirement_id in sorted(G0A_REQUIRED_REQUIREMENT_IDS)
    ]
    readiness = existing_requirements.get("R0A-07")
    if isinstance(readiness, dict):
        readiness["status"] = "incomplete"
        readiness["reason"] = "DeliveryReadiness v1 has no complete R0A/R1 work-package records"
    contract = existing_requirements.get("R0A-06")
    if isinstance(contract, dict):
        refs = contract.setdefault("evidenceRefs", [])
        for relative in (
            GATE_EVIDENCE_SCHEMA_PATH.as_posix(),
            GATE_POLICY_SCHEMA_PATH.as_posix(),
            GATE_POLICY_PATH.as_posix(),
            "docs/governance/GATE_EVIDENCE_MODEL_V3.md",
        ):
            for item in evidence_by_path.get(relative, []):
                evidence_id = item.get("evidenceId")
                if isinstance(evidence_id, str) and evidence_id not in refs:
                    refs.append(evidence_id)
        contract["status"] = "ready_for_independent_review"
        contract["reason"] = "GateEvidence v3 and policy v2 implementation candidate requires independent review"
    _synchronize_gate_contract_inputs(root, evidence)
    return True


def refresh_evidence(
    root: Path,
    evidence: dict[str, Any],
) -> tuple[dict[str, Any], WorkspaceFingerprint]:
    """Refresh generated fields without claiming that quality commands passed."""

    refreshed = copy.deepcopy(evidence)
    migrated = _migrate_manifest_v3(root, refreshed)
    refreshed["evidence"] = [
        _normalise_evidence_item_v3(item) for item in refreshed.get("evidence", []) if isinstance(item, dict)
    ]
    _synchronize_gate_contract_inputs(root, refreshed)
    _synchronize_required_software_items(refreshed)
    fingerprint = fingerprint_workspace(root)
    previous_source = refreshed.get("source", {})
    previous_sha = previous_source.get("worktreeInventorySha256")
    previous_subject = previous_source.get("subjectCommit")
    previous_tree = previous_source.get("subjectTree")
    retain_attested_subject = (
        refreshed.get("decision") == "passed" and isinstance(previous_subject, str) and isinstance(previous_tree, str)
    )
    subject_commit = previous_subject if retain_attested_subject else fingerprint.base_commit
    subject_tree = previous_tree if retain_attested_subject else _commit_tree(root, fingerprint.base_commit)
    source = {
        "subjectCommit": subject_commit,
        "subjectTree": subject_tree,
        "worktreeDirty": fingerprint.dirty,
        "worktreeStatusEntryCount": fingerprint.status_entry_count,
        "worktreeFingerprintSchema": FINGERPRINT_SCHEMA,
        "worktreeInventorySha256": fingerprint.sha256,
        "excludedGeneratedPaths": [path.as_posix() for path in GENERATED_PATHS],
        "verificationRuns": [],
    }
    same_subject = previous_subject == subject_commit and previous_tree == subject_tree
    if previous_sha == fingerprint.sha256 and same_subject and not migrated:
        existing_runs = previous_source.get("verificationRuns")
        if isinstance(existing_runs, list):
            source["verificationRuns"] = [
                normalised
                for run in existing_runs
                if isinstance(run, dict) and (normalised := _normalise_verification_run_v3(run)) is not None
            ]
    refreshed["source"] = source

    if previous_sha != fingerprint.sha256 or not same_subject or migrated:
        _mark_software_stale(refreshed)
        _set_verified_worktree_claims(
            refreshed,
            verified=False,
            dirty=fingerprint.dirty,
        )
    _refresh_hashed_evidence(root, refreshed)
    _refresh_clean_checkout_requirement(refreshed, fingerprint)
    _synchronise_terminal_blockers(refreshed)
    return refreshed, fingerprint


def _front_matter(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    parsed = yaml.safe_load("\n".join(lines[1:end]))
    return parsed if isinstance(parsed, dict) else {}


def _gate_policy_issues(
    evidence: dict[str, Any],
    *,
    root: Path,
) -> list[str]:
    policy = json.loads((root / GATE_POLICY_PATH).read_text(encoding="utf-8"))
    issues: list[str] = []
    requirement_by_id = {item.get("id"): item for item in evidence.get("requirements", []) if isinstance(item, dict)}
    evidence_by_key = {
        (item.get("path"), item.get("kind")): item for item in evidence.get("evidence", []) if isinstance(item, dict)
    }
    evidence_by_id = {
        item.get("evidenceId"): item
        for item in evidence.get("evidence", [])
        if isinstance(item, dict) and isinstance(item.get("evidenceId"), str)
    }
    non_waivable = set(policy.get("nonWaivableRequirementIds", []))
    for requirement_id, rule in policy.get("requirements", {}).items():
        requirement = requirement_by_id.get(requirement_id)
        if requirement is None:
            issues.append(f"gate policy requirement is missing: {requirement_id}")
            continue
        if requirement.get("status") == "waived" and requirement_id in non_waivable:
            issues.append(f"requirement is not waivable: {requirement_id}")
        if rule.get("requiresCleanCommittedSubject"):
            source = evidence.get("source", {})
            if (
                not isinstance(source, dict)
                or source.get("worktreeDirty") is not False
                or source.get("worktreeStatusEntryCount") != 0
            ):
                issues.append(f"{requirement_id} requires a clean committed subject")
        if rule.get("requiresAssignedOwner") and not _assigned_identity(evidence.get("owner")):
            issues.append(f"{requirement_id} requires an assigned gate owner")
        if rule.get("requiresIndependentReviewer"):
            owner_account = _identity_account_id(evidence.get("owner"))
            reviewer_accounts = {
                account for reviewer in evidence.get("reviewers", []) if (account := _identity_account_id(reviewer))
            }
            if not reviewer_accounts:
                issues.append(f"{requirement_id} requires an independent reviewer")
            if owner_account and owner_account in reviewer_accounts:
                issues.append(f"{requirement_id} gate owner cannot self-review")
        for relative in rule.get("requiredPaths", []):
            if not (root / relative).is_file():
                issues.append(f"required policy path is missing: {relative}")
        for decision in rule.get("requiredDecisions", []):
            relative = decision["path"]
            actual = _front_matter(root / relative).get("decision_status")
            if actual != decision["status"]:
                issues.append(
                    f"{requirement_id} requires {relative} decision_status "
                    f"{decision['status']}, got {actual or 'missing'}"
                )
        for expected in rule.get("requiredEvidence", []):
            key = (expected["path"], expected["kind"])
            item = evidence_by_key.get(key)
            if item is None:
                issues.append(f"{requirement_id} lacks evidence {expected['kind']}:{expected['path']}")
                continue
            accepted_results = set(expected["acceptedResults"])
            if item.get("result") not in accepted_results:
                issues.append(
                    f"{requirement_id} evidence {expected['path']} has result "
                    f"{item.get('result')!r}; expected one of {sorted(accepted_results)}"
                )
        terminal_rule = rule.get("terminalAcceptance")
        if isinstance(terminal_rule, dict):
            terminal = requirement.get("terminalEvidence")
            if not isinstance(terminal, dict):
                issues.append(f"{requirement_id} terminal evidence declaration is missing")
                continue
            expected_terminal = {
                "path": terminal_rule["evidencePath"],
                "kind": terminal_rule["kind"],
                "result": terminal_rule["acceptedResult"],
            }
            for field, expected_value in expected_terminal.items():
                if terminal.get(field) != expected_value:
                    issues.append(f"{requirement_id} terminal evidence {field} is not {expected_value!r}")
            terminal_sha = terminal.get("sha256")
            if not _is_sha256(terminal_sha):
                issues.append(f"{requirement_id} terminal evidence sha256 is missing")
            evidence_id = terminal.get("evidenceId")
            item = evidence_by_id.get(evidence_id)
            if item is None:
                issues.append(f"{requirement_id} terminal evidenceId is unresolved")
            else:
                for field in ("path", "kind", "result", "sha256"):
                    if item.get(field) != terminal.get(field):
                        issues.append(f"{requirement_id} terminal evidence mirror differs at {field}")
            if terminal_rule.get("requiresRemoteProvenance"):
                terminal_provenance = terminal.get("remoteProvenance")
                item_provenance = item.get("remoteProvenance") if isinstance(item, dict) else None
                if not isinstance(terminal_provenance, dict):
                    issues.append(f"{requirement_id} terminal evidence lacks remote provenance")
                if item_provenance != terminal_provenance:
                    issues.append(f"{requirement_id} terminal remote provenance mirror differs")
    return issues


def _valid_reference_uri(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    if parsed.scheme == "https":
        return bool(parsed.netloc)
    return parsed.scheme == "urn" and bool(parsed.path)


def _delivery_readiness_issues(
    evidence: dict[str, Any],
    *,
    now: datetime,
) -> list[str]:
    readiness = evidence.get("deliveryReadiness")
    if not isinstance(readiness, dict):
        return ["DeliveryReadinessEvidence is missing"]
    issues: list[str] = []
    if readiness.get("schemaVersion") != DELIVERY_READINESS_SCHEMA_VERSION:
        issues.append("DeliveryReadinessEvidence schemaVersion is invalid")
    records = readiness.get("workPackages")
    if not isinstance(records, list):
        return issues + ["DeliveryReadinessEvidence workPackages are missing"]
    package_ids = [record.get("id") for record in records if isinstance(record, dict)]
    if len(package_ids) != len(set(package_ids)):
        issues.append("DeliveryReadinessEvidence contains duplicate work-package IDs")
    package_id_set = {item for item in package_ids if isinstance(item, str)}
    if package_id_set != G0A_REQUIRED_DELIVERY_WORK_PACKAGE_IDS:
        issues.append(
            "DeliveryReadinessEvidence work-package IDs differ from policy; "
            f"missing={sorted(G0A_REQUIRED_DELIVERY_WORK_PACKAGE_IDS - package_id_set)}; "
            f"unexpected={sorted(package_id_set - G0A_REQUIRED_DELIVERY_WORK_PACKAGE_IDS)}"
        )

    source = evidence.get("source", {})
    subject_commit = source.get("subjectCommit")
    subject_tree = source.get("subjectTree")
    for record in records:
        if not isinstance(record, dict):
            issues.append("DeliveryReadinessEvidence records must be objects")
            continue
        package_id = str(record.get("id", "<unknown>"))
        if record.get("status") != "ready":
            issues.append(f"{package_id} DeliveryReadiness status is not ready")
        owner = record.get("owner")
        owner_account = _identity_account_id(owner)
        if not isinstance(owner, dict) or not owner_account:
            issues.append(f"{package_id} DeliveryReadiness owner is unassigned")
        reviewers = record.get("reviewers")
        if not isinstance(reviewers, list) or not reviewers:
            issues.append(f"{package_id} DeliveryReadiness independent reviewer is unassigned")
        else:
            reviewer_accounts: set[str] = set()
            for reviewer in reviewers:
                account = _identity_account_id(reviewer)
                if not isinstance(reviewer, dict) or not account:
                    issues.append(f"{package_id} DeliveryReadiness reviewer is invalid")
                    continue
                if account == owner_account:
                    issues.append(f"{package_id} DeliveryReadiness owner cannot self-review")
                if account in reviewer_accounts:
                    issues.append(f"{package_id} DeliveryReadiness reviewer is duplicated")
                reviewer_accounts.add(account)
                if reviewer.get("reviewedSubjectCommit") != subject_commit:
                    issues.append(f"{package_id} DeliveryReadiness reviewer targets another subject commit")
                if reviewer.get("reviewedSubjectTree") != subject_tree:
                    issues.append(f"{package_id} DeliveryReadiness reviewer targets another subject tree")
                if reviewer.get("conflictOfInterest") is not False:
                    issues.append(f"{package_id} DeliveryReadiness conflict declaration is not clear")
                if not _valid_reference_uri(reviewer.get("reviewUrl")):
                    issues.append(f"{package_id} DeliveryReadiness reviewUrl is invalid")
                reviewed_at = reviewer.get("reviewedAt")
                try:
                    _validated_verified_at(str(reviewed_at))
                    if _iso_moment(str(reviewed_at)) > now + timedelta(minutes=5):
                        issues.append(f"{package_id} DeliveryReadiness review is in the future")
                except ValueError:
                    issues.append(f"{package_id} DeliveryReadiness reviewedAt is not UTC")

        capacity = record.get("capacity")
        if not isinstance(capacity, dict):
            issues.append(f"{package_id} DeliveryReadiness capacity is missing")
        else:
            if not isinstance(capacity.get("availablePersonHours"), (int, float)) or (
                capacity["availablePersonHours"] <= 0
            ):
                issues.append(f"{package_id} DeliveryReadiness capacity must be positive")
            try:
                capacity_start = date.fromisoformat(str(capacity.get("periodStart")))
                capacity_end = date.fromisoformat(str(capacity.get("periodEnd")))
                if capacity_end < capacity_start:
                    issues.append(f"{package_id} DeliveryReadiness capacity period is reversed")
            except ValueError:
                issues.append(f"{package_id} DeliveryReadiness capacity dates are invalid")

        estimate = record.get("estimate")
        if not isinstance(estimate, dict):
            issues.append(f"{package_id} DeliveryReadiness estimate is missing")
        else:
            values = [
                estimate.get("optimistic"),
                estimate.get("mostLikely"),
                estimate.get("pessimistic"),
            ]
            if (
                estimate.get("method") != "three-point"
                or estimate.get("unit") != "person-hours"
                or any(not isinstance(value, (int, float)) or value <= 0 for value in values)
                or not (values[0] <= values[1] <= values[2])
            ):
                issues.append(f"{package_id} DeliveryReadiness three-point estimate is invalid")

        wip = record.get("wip")
        if (
            not isinstance(wip, dict)
            or not isinstance(wip.get("globalLimit"), int)
            or wip["globalLimit"] < 1
            or wip.get("slot")
            not in {
                "WIP-GATE",
                "WIP-PRODUCT",
                "QUEUED-DOMAIN",
            }
        ):
            issues.append(f"{package_id} DeliveryReadiness WIP contract is invalid")

        timebox = record.get("timebox")
        if not isinstance(timebox, dict):
            issues.append(f"{package_id} DeliveryReadiness timebox is missing")
        else:
            try:
                starts_at = _iso_moment(str(timebox.get("startsAt")))
                ends_at = _iso_moment(str(timebox.get("endsAt")))
                _validated_verified_at(str(timebox.get("startsAt")))
                _validated_verified_at(str(timebox.get("endsAt")))
                if ends_at <= starts_at:
                    issues.append(f"{package_id} DeliveryReadiness timebox is empty or reversed")
                if ends_at <= now:
                    issues.append(f"{package_id} DeliveryReadiness timebox is expired")
            except ValueError:
                issues.append(f"{package_id} DeliveryReadiness timebox is not UTC")

        if not isinstance(record.get("scopeReductionRule"), str) or not record["scopeReductionRule"].strip():
            issues.append(f"{package_id} DeliveryReadiness scope reduction rule is missing")
        if not _valid_reference_uri(record.get("approvalReference")):
            issues.append(f"{package_id} DeliveryReadiness approval reference is invalid")
        try:
            expires_at = str(record.get("expiresAt"))
            _validated_verified_at(expires_at)
            if _iso_moment(expires_at) <= now:
                issues.append(f"{package_id} DeliveryReadiness record is expired")
        except ValueError:
            issues.append(f"{package_id} DeliveryReadiness expiresAt is not UTC")
    return issues


def _subject_attestation_issues(
    evidence: dict[str, Any],
    *,
    root: Path,
) -> list[str]:
    source = evidence.get("source", {})
    subject = source.get("subjectCommit")
    subject_tree = source.get("subjectTree")
    if not isinstance(subject, str) or not isinstance(subject_tree, str):
        return ["subject commit/tree metadata is missing"]
    issues: list[str] = []
    try:
        actual_tree = _commit_tree(root, subject)
    except subprocess.CalledProcessError:
        return [f"subject commit is unavailable: {subject}"]
    if actual_tree != subject_tree:
        issues.append("subjectTree does not match subjectCommit")

    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", subject, head],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        issues.append("subjectCommit is not an ancestor of the attestation revision")
    else:
        changed_raw = _git(root, "diff", "--name-only", "-z", f"{subject}..{head}")
        changed = {item.decode("utf-8", errors="surrogateescape") for item in changed_raw.split(b"\0") if item}
        allowed = {path.as_posix() for path in GENERATED_PATHS}
        unexpected = sorted(changed - allowed)
        if unexpected:
            issues.append("attestation revision changes non-generated paths: " + ", ".join(unexpected))

    actual_fingerprint = fingerprint_workspace(root)
    expected_workspace = {
        "worktreeDirty": actual_fingerprint.dirty,
        "worktreeStatusEntryCount": actual_fingerprint.status_entry_count,
        "worktreeFingerprintSchema": FINGERPRINT_SCHEMA,
        "worktreeInventorySha256": actual_fingerprint.sha256,
    }
    for field, actual_value in expected_workspace.items():
        if source.get(field) != actual_value:
            issues.append(f"source {field} does not match the current workspace")
    return issues


def _trusted_attestation_issues(evidence: dict[str, Any], *, root: Path) -> list[str]:
    """Keep pass issuance closed until external trust verification exists.

    Account IDs, provider URLs/digests and accepted-terminal mirrors below are
    declarations. Checking their JSON shape or repository hash cannot establish
    account consent, provider authenticity or terminal-payload acceptance.
    A future reviewed verifier must bind all three to this exact subject. There
    is deliberately no CLI flag or evidence field that disables this boundary.
    """
    return [
        "external attestation verification is unavailable: authenticated account consent, "
        "provider results and independent terminal-payload validation are not implemented"
    ]


def validate_passed_decision(
    evidence: dict[str, Any],
    *,
    root: Path = ROOT,
    now: datetime | None = None,
    verify_current_workspace: bool = True,
) -> None:
    validate_gate_evidence_manifest(evidence, root=root, now=now)
    if evidence.get("decision") != "passed":
        return

    issues: list[str] = _trusted_attestation_issues(evidence, root=root)
    requirements = evidence.get("requirements", [])
    requirement_by_id = {item.get("id"): item for item in requirements if isinstance(item, dict)}
    failing_requirements = [
        str(item.get("id", "<unknown>"))
        for item in requirements
        if not isinstance(item, dict) or item.get("status") not in {"passed", "waived"}
    ]
    if failing_requirements:
        issues.append(f"requirements unresolved: {', '.join(failing_requirements)}")

    waivers = evidence.get("waivers", [])
    waiver_requirement_ids: set[str] = set()
    current_moment = now or datetime.now(timezone.utc)
    if current_moment.tzinfo is None:
        current_moment = current_moment.replace(tzinfo=timezone.utc)
    current_moment = current_moment.astimezone(timezone.utc)
    issues.extend(
        _delivery_readiness_issues(
            evidence,
            now=current_moment,
        )
    )
    for waiver in waivers:
        if not isinstance(waiver, dict):
            issues.append("waiver entries must be objects")
            continue
        requirement_id = waiver.get("requirementId")
        missing = [
            field
            for field in ("requirementId", "approvedBy", "reason", "expiresAt")
            if not isinstance(waiver.get(field), str) or not waiver[field].strip()
        ]
        if missing:
            issues.append("waiver is missing required fields: " + ", ".join(sorted(missing)))
        expires_at = waiver.get("expiresAt")
        if isinstance(expires_at, str) and expires_at.strip():
            try:
                expiry = _iso_moment(expires_at.strip())
            except ValueError:
                issues.append("waiver expiresAt is not an ISO date or date-time")
            else:
                if expiry <= current_moment:
                    issues.append(f"waiver is expired: {requirement_id}")
        if isinstance(requirement_id, str):
            waiver_requirement_ids.add(requirement_id)
            requirement = requirement_by_id.get(requirement_id)
            if requirement is None or requirement.get("status") != "waived":
                issues.append(f"waiver is not linked to a waived requirement: {requirement_id}")

    waived_requirements = {
        str(item.get("id")) for item in requirements if isinstance(item, dict) and item.get("status") == "waived"
    }
    missing_waivers = sorted(waived_requirements - waiver_requirement_ids)
    if missing_waivers:
        issues.append("waived requirements lack registered waivers: " + ", ".join(missing_waivers))

    software_items = [
        item
        for item in evidence.get("evidence", [])
        if isinstance(item, dict)
        and item.get("kind") == "SoftwareVerificationEvidence"
        and isinstance(item.get("protocol"), str)
    ]
    if not software_items:
        issues.append("software verification evidence is missing")
    protocol_items: dict[str, dict[str, Any]] = {}
    for item in software_items:
        protocol = item.get("protocol")
        if not isinstance(protocol, str) or not protocol.strip():
            issues.append("software verification protocol is missing")
            continue
        if protocol in protocol_items:
            issues.append(f"duplicate software verification protocol: {protocol}")
        protocol_items[protocol] = item
    software_failures = [
        str(item.get("protocol", item.get("path", "<unknown>")))
        for item in software_items
        if item.get("result") != "pass"
    ]
    if software_failures:
        issues.append("software verification is not passing: " + ", ".join(software_failures))
    for protocol, item in protocol_items.items():
        if item.get("result") != "pass":
            continue
        mode = item.get("verificationMode")
        if mode == "direct":
            if not isinstance(item.get("executedCommand"), str) or not item["executedCommand"].strip():
                issues.append(f"direct verification lacks executed command: {protocol}")
        else:
            issues.append(f"passing verification has invalid mode: {protocol}")

    if evidence.get("blockers"):
        issues.append("blocking findings remain")

    owner = evidence.get("owner")
    if not _assigned_identity(owner):
        issues.append("owner is unassigned")
    if not isinstance(owner, dict):
        issues.append("passed owner identity must be a structured account")
    reviewers = evidence.get("reviewers")
    if not isinstance(reviewers, list) or not reviewers:
        issues.append("independent reviewers are unassigned")
    else:
        reviewer_names = [_identity_name(reviewer) for reviewer in reviewers]
        if any(not _assigned_identity(reviewer) for reviewer in reviewers):
            issues.append("reviewer entries must name assigned reviewers")
        if _identity_name(owner) in reviewer_names:
            issues.append("owner cannot be the independent reviewer")
        reviewer_roles: set[str] = set()
        reviewer_account_ids: set[str] = set()
        for reviewer in reviewers:
            if not isinstance(reviewer, dict):
                issues.append("passed reviewers must use structured attestations")
                continue
            reviewer_roles.update(role for role in reviewer.get("roles", []) if isinstance(role, str))
            account_id = _identity_account_id(reviewer)
            if account_id:
                if account_id in reviewer_account_ids:
                    issues.append("duplicate reviewer stable account ID")
                reviewer_account_ids.add(account_id)
            if reviewer.get("reviewedSubjectCommit") != evidence.get("source", {}).get("subjectCommit"):
                issues.append("reviewer attestation targets a different subject commit")
            if reviewer.get("reviewedSubjectTree") != evidence.get("source", {}).get("subjectTree"):
                issues.append("reviewer attestation targets a different subject tree")
            if reviewer.get("decision") != "accepted":
                issues.append("reviewer attestation is not accepted")
            if reviewer.get("conflictOfInterest") is not False:
                issues.append("reviewer conflict-of-interest declaration is not clear")
            if not _valid_reference_uri(reviewer.get("reviewUrl")):
                issues.append("reviewer attestation reviewUrl is invalid")
            reviewed_at = reviewer.get("reviewedAt")
            try:
                _validated_verified_at(str(reviewed_at))
                if _iso_moment(str(reviewed_at)) > current_moment + timedelta(minutes=5):
                    issues.append("reviewer attestation is in the future")
            except ValueError:
                issues.append("reviewer attestation reviewedAt is not UTC")
        missing_roles = {"architecture", "migration"} - reviewer_roles
        if missing_roles:
            issues.append("independent reviewer roles are missing: " + ", ".join(sorted(missing_roles)))
        owner_account_id = _identity_account_id(owner)
        if owner_account_id and owner_account_id in reviewer_account_ids:
            issues.append("owner account cannot be an independent reviewer")
    owner_name = _identity_name(owner)
    for waiver in waivers:
        if not isinstance(waiver, dict):
            continue
        approver = _identity_name(waiver.get("approvedBy"))
        if not _assigned_identity(waiver.get("approvedBy")):
            issues.append("waiver approver is unassigned")
        if approver == owner_name:
            issues.append("owner cannot approve a waiver for the same gate")

    source = evidence.get("source")
    if not isinstance(source, dict):
        issues.append("source metadata is missing")
    else:
        if source.get("worktreeDirty") is not False:
            issues.append("worktree is not clean")
        inventory_sha = source.get("worktreeInventorySha256")
        if not _is_sha256(inventory_sha):
            issues.append("worktree fingerprint is missing or invalid")
        verification_runs = [run for run in source.get("verificationRuns", []) if isinstance(run, dict)]
        latest_run = verification_runs[-1] if verification_runs else None
        if latest_run is None or latest_run.get("result") != "pass":
            issues.append("latest verification run is not passing")
        claimed_remote_runs = [
            run
            for run in verification_runs
            if run.get("result") == "pass" and isinstance(run.get("remoteProvenance"), dict)
        ]
        claimed_platforms = {run.get("platformFamily") for run in claimed_remote_runs}
        missing_trusted_platforms = {"windows", "linux"} - claimed_platforms
        if missing_trusted_platforms:
            issues.append(
                "trusted cross-platform verification is missing: " + ", ".join(sorted(missing_trusted_platforms))
            )
        current_passing_runs = [latest_run] if latest_run is not None and latest_run.get("result") == "pass" else []
        for run in current_passing_runs:
            protocols = run.get("protocols")
            if not isinstance(protocols, list) or set(protocols) != G0A_REQUIRED_PROTOCOLS:
                issues.append(f"verification run protocols are incomplete: {run.get('runId')}")
            environment = run.get("environment")
            if not isinstance(environment, dict):
                issues.append(f"verification run environment is missing: {run.get('runId')}")
                continue
            missing_environment = sorted({"os", "architecture", "toolchain", "lockFileSha256"} - environment.keys())
            if missing_environment:
                issues.append("verification environment lacks: " + ", ".join(missing_environment))
            lock_hashes = environment.get("lockFileSha256")
            if not isinstance(lock_hashes, dict) or set(lock_hashes) != {path.as_posix() for path in LOCK_FILES}:
                issues.append("verification lock-file hashes are incomplete")
            elif any(not _is_sha256(value) for value in lock_hashes.values()):
                issues.append("verification lock-file hashes are invalid")
            for field in {"os", "architecture"}:
                if not isinstance(environment.get(field), str) or not environment[field].strip():
                    issues.append(f"verification environment field is invalid: {field}")
            toolchain = environment.get("toolchain")
            if not isinstance(toolchain, dict):
                issues.append("verification toolchain is missing")
                continue
            for field in {"python", "rustc", "cargo", "node"}:
                if not isinstance(toolchain.get(field), str) or not toolchain[field].strip():
                    issues.append(f"verification toolchain field is invalid: {field}")
            if not _tool_version_matches_release(
                toolchain.get("rustc"),
                tool="rustc",
                required_version=REQUIRED_RUST_VERSION,
            ):
                issues.append("recorded rustc version does not exactly match the workspace MSRV")
            if not _tool_version_matches_release(
                toolchain.get("cargo"),
                tool="cargo",
                required_version=REQUIRED_RUST_VERSION,
            ):
                issues.append("recorded cargo version does not exactly match the workspace MSRV")
        if current_passing_runs:
            latest_finished_at = str(current_passing_runs[0]["finishedAt"])
            if evidence.get("decisionDate") != latest_finished_at[:10]:
                issues.append("decisionDate does not match the latest passing run")

    claims = evidence.get("claims", {})
    if "G0A has passed" in claims.get("forbidden", []):
        issues.append("passed claim remains forbidden")
    if "G0A has passed" not in claims.get("allowed", []):
        issues.append("passed claim is not allowed")

    issues.extend(_gate_policy_issues(evidence, root=root))

    if verify_current_workspace:
        issues.extend(_subject_content_issues(evidence, root=root))
        issues.extend(_subject_attestation_issues(evidence, root=root))

    if issues:
        raise ValueError("GateEvidence cannot claim passed: " + "; ".join(issues))


def _identity_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip().casefold()
    if isinstance(value, dict):
        for key in ("displayName", "name", "login"):
            if isinstance(value.get(key), str):
                return value[key].strip().casefold()
    return None


def _identity_account_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    account_id = value.get("stableAccountId")
    if not isinstance(account_id, str):
        return None
    account_id = account_id.strip()
    return account_id or None


def _assigned_identity(value: Any) -> bool:
    name = _identity_name(value)
    return bool(name and name not in {"unassigned", "none", "tbd"})


def render_status(evidence: dict[str, Any]) -> str:
    """Render STATUS.md entirely from GateEvidence."""

    source = evidence["source"]
    verification_runs = [run for run in source.get("verificationRuns", []) if isinstance(run, dict)]
    latest_run = verification_runs[-1] if verification_runs else None
    verified_at = (
        str(latest_run["finishedAt"])
        if evidence.get("decision") == "passed" and latest_run is not None and latest_run.get("result") == "pass"
        else "not-verified"
    )
    lines = [
        "---",
        "document_type: operational-status",
        "decision_status: not-applicable",
        "implementation_status: generated",
        "normative_scope: current",
        f"last_verified: {verified_at}",
        f"base_commit: {source['subjectCommit']}",
        f"worktree_fingerprint: {source['worktreeInventorySha256']}",
        "generated_from: docs/G0A_GATE_EVIDENCE_2026-07-17.json",
        "---",
        "",
        "# Telysta 当前状态",
        "",
        "> 此文件由 `scripts/generate_gate_evidence.py` 生成，不得手工维护状态或测试数量。",
        "",
        "## Gate",
        "",
        "| Gate | Decision | Worktree | Verified |",
        "|---|---|---|---|",
        (
            f"| {evidence['gateId']} | `{evidence['decision']}` | "
            f"{'dirty' if source['worktreeDirty'] else 'clean'} "
            f"({source['worktreeStatusEntryCount']} entries) | "
            f"{verified_at} |"
        ),
        "",
        f"- Subject commit: `{source['subjectCommit']}`",
        f"- Subject tree: `{source['subjectTree']}`",
        f"- Fingerprint: `{source['worktreeInventorySha256']}`",
        f"- Fingerprint schema: `{source['worktreeFingerprintSchema']}`",
        "- 当前实现能力见 [Current Architecture](./architecture/CURRENT.md)。",
        "- 当前执行顺序见 [产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)。",
        "",
        "## Requirements",
        "",
        "| ID | Status | Name |",
        "|---|---|---|",
    ]
    lines.extend(f"| {item['id']} | `{item['status']}` | {item['name']} |" for item in evidence["requirements"])
    lines.extend(["", "## 当前允许声明", ""])
    lines.extend(f"- {claim}" for claim in evidence["claims"]["allowed"])
    lines.extend(["", "## 当前禁止声明", ""])
    lines.extend(f"- {claim}" for claim in evidence["claims"]["forbidden"])
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- `{item['id']}`：{item['summary']}" for item in evidence["blockers"])
    lines.extend(
        [
            "",
            "## 下一决策",
            "",
            evidence["nextDecision"],
            "",
        ]
    )
    return "\n".join(lines)


def write_generated_outputs(
    root: Path,
    evidence_path: Path,
    status_path: Path,
    evidence: dict[str, Any],
) -> None:
    evidence_output = root / evidence_path
    status_output = root / status_path
    evidence_output.parent.mkdir(parents=True, exist_ok=True)
    status_output.parent.mkdir(parents=True, exist_ok=True)
    evidence_payload = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    status_payload = render_status(evidence)
    previous_evidence = evidence_output.read_text(encoding="utf-8") if evidence_output.is_file() else None
    previous_status = status_output.read_text(encoding="utf-8") if status_output.is_file() else None
    evidence_temporary = _prepare_atomic_text(evidence_output, evidence_payload)
    try:
        _replace_prepared_text(evidence_temporary, evidence_output)
        status_temporary = _prepare_atomic_text(status_output, status_payload)
        # GateEvidence is authoritative and is replaced first. A blocked
        # checkpoint remains authoritative if the derived STATUS replacement
        # fails. A passed publication is rolled back to its prior blocked
        # checkpoint so a partial two-file publication cannot expose a pass.
        _replace_prepared_text(status_temporary, status_output)
    except Exception:
        if evidence.get("decision") == "passed":
            if previous_evidence is None:
                evidence_output.unlink(missing_ok=True)
            else:
                _atomic_replace_text(evidence_output, previous_evidence)
            if previous_status is None:
                status_output.unlink(missing_ok=True)
            else:
                _atomic_replace_text(status_output, previous_status)
        else:
            # A stale human-readable pass is less safe than an absent derived
            # file. GateEvidence remains the source and the next invocation
            # deterministically rebuilds STATUS.
            status_output.unlink(missing_ok=True)
        raise
    finally:
        evidence_temporary.unlink(missing_ok=True)
        if "status_temporary" in locals():
            status_temporary.unlink(missing_ok=True)


def _prepare_atomic_text(path: Path, payload: str) -> Path:
    """Flush a same-directory temporary file ready for atomic replacement."""

    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
            newline="",
        ) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def _replace_prepared_text(temporary_path: Path, path: Path) -> None:
    os.replace(temporary_path, path)
    _fsync_directory(path.parent)


def _atomic_replace_text(path: Path, payload: str) -> None:
    """Durably replace one generated file without exposing partial contents."""

    temporary_path = _prepare_atomic_text(path, payload)
    try:
        _replace_prepared_text(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    """Persist a replacement's directory entry where the platform supports it."""

    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _command_text(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def _record_direct_result(
    item: dict[str, Any],
    *,
    command: list[str],
    passed: bool,
    details: str,
) -> None:
    item["result"] = "pass" if passed else "fail"
    item["details"] = details
    item["verificationMode"] = "direct"
    item["executedCommand"] = _command_text(command)
    item.pop("coveredBy", None)


def _tool_version(root: Path, *command: str) -> str:
    completed = subprocess.run(
        list(command),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return completed.stdout.strip()
    detail = completed.stderr.strip() or completed.stdout.strip()
    return f"unavailable ({detail or f'exit {completed.returncode}'})"


def _lock_file_hashes(root: Path) -> dict[str, str]:
    subject = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    hashes: dict[str, str] = {}
    for relative in LOCK_FILES:
        try:
            payload = _subject_blob(root, subject, relative.as_posix())
        except subprocess.CalledProcessError:
            raise FileNotFoundError(f"verification lock file is missing: {relative}")
        hashes[relative.as_posix()] = hashlib.sha256(payload).hexdigest()
    return hashes


def _marker_applies(marker_spec: Any, groups: set[str]) -> bool:
    environment = default_environment()
    if marker_spec is None:
        return True
    if isinstance(marker_spec, str):
        return Marker(marker_spec).evaluate(environment)
    if isinstance(marker_spec, dict):
        for group in groups:
            group_marker = marker_spec.get(group)
            if group_marker is None:
                return True
            if isinstance(group_marker, str) and Marker(group_marker).evaluate(environment):
                return True
        return False
    raise ValueError(f"unsupported poetry.lock marker shape: {marker_spec!r}")


def _locked_python_distributions(root: Path) -> dict[str, str]:
    lock = tomllib.loads((root / "poetry.lock").read_text(encoding="utf-8"))
    expected: dict[str, str] = {}
    for package in lock.get("package", []):
        groups = set(package.get("groups", ["main"]))
        selected_groups = groups & PYTHON_LOCK_GROUPS
        if not selected_groups or not _marker_applies(package.get("markers"), selected_groups):
            continue
        name = canonicalize_name(package["name"])
        version = str(package["version"])
        previous = expected.get(name)
        if previous is not None and previous != version:
            raise ValueError(f"poetry.lock selects multiple versions for {name}: {previous}, {version}")
        expected[name] = version
    return dict(sorted(expected.items()))


def _installed_python_distributions() -> dict[str, str]:
    installed: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        installed[canonicalize_name(name)] = distribution.version
    return dict(sorted(installed.items()))


def _python_environment_evidence(root: Path) -> dict[str, Any]:
    expected = _locked_python_distributions(root)
    installed = _installed_python_distributions()
    compared_installed = {
        name: version for name, version in installed.items() if name not in ALLOWED_UNMANAGED_PYTHON_DISTRIBUTIONS
    }
    mismatches: list[str] = []
    for name in sorted(expected.keys() - compared_installed.keys()):
        mismatches.append(f"missing {name}=={expected[name]}")
    for name in sorted(compared_installed.keys() - expected.keys()):
        mismatches.append(f"unexpected {name}=={compared_installed[name]}")
    for name in sorted(expected.keys() & compared_installed.keys()):
        if expected[name] != compared_installed[name]:
            mismatches.append(f"version {name}: locked {expected[name]}, installed {compared_installed[name]}")
    payload = json.dumps(
        installed,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "pythonInstalledDistributionsSha256": hashlib.sha256(payload).hexdigest(),
        "pythonLockStatus": "match" if not mismatches else "mismatch",
        "pythonLockMismatches": mismatches,
    }


def _workspace_rust_version(root: Path) -> str:
    manifest = tomllib.loads((root / "Cargo.toml").read_text(encoding="utf-8"))
    return str(manifest["workspace"]["package"]["rust-version"])


def _tool_version_matches_release(
    output: Any,
    *,
    tool: str,
    required_version: str,
) -> bool:
    if not isinstance(output, str) or not output.startswith(f"{tool} "):
        return False
    try:
        actual = Version(output.split()[1])
        required = Version(required_version)
    except (IndexError, InvalidVersion):
        return False
    return actual == required


def _verification_environment(root: Path) -> dict[str, Any]:
    required_rust_version = _workspace_rust_version(root)
    pinned_rust_version = _pinned_rust_version(root)
    rustc_version = _tool_version(
        root,
        "rustc",
        f"+{pinned_rust_version}",
        "--version",
    )
    cargo_version = _tool_version(
        root,
        "cargo",
        f"+{pinned_rust_version}",
        "--version",
    )
    environment = {
        "platform": platform.platform(),
        "pythonExecutable": str(Path(sys.executable).absolute()),
        "pythonVersion": platform.python_version(),
        "rustcVersion": rustc_version,
        "cargoVersion": cargo_version,
        "requiredRustVersion": required_rust_version,
        "rustVersionMeetsWorkspace": (
            required_rust_version == pinned_rust_version == REQUIRED_RUST_VERSION
            and _tool_version_matches_release(
                rustc_version,
                tool="rustc",
                required_version=required_rust_version,
            )
            and _tool_version_matches_release(
                cargo_version,
                tool="cargo",
                required_version=required_rust_version,
            )
        ),
        "nodeVersion": _tool_version(root, "node", "--version"),
        "lockFileSha256": _lock_file_hashes(root),
    }
    environment.update(_python_environment_evidence(root))
    return environment


def _safe_tool_version(root: Path, *command: str) -> str:
    try:
        return _tool_version(root, *command)
    except Exception as error:  # noqa: BLE001 - failure evidence must survive tooling faults.
        return f"unavailable ({type(error).__name__}: {error})"


def _fallback_verification_environment(
    root: Path,
) -> dict[str, Any] | None:
    """Capture a complete honest v2 environment, or decline to create a run."""

    try:
        required_rust_version = _workspace_rust_version(root)
        pinned_rust_version = _pinned_rust_version(root)
        python_environment = _python_environment_evidence(root)
        lock_hashes = _lock_file_hashes(root)
    except Exception:  # noqa: BLE001 - v2 cannot represent a partial environment.
        return None
    environment = {
        "platform": platform.platform() or "unavailable",
        "pythonExecutable": str(Path(sys.executable).absolute()),
        "pythonVersion": platform.python_version() or "unavailable",
        "rustcVersion": _safe_tool_version(
            root,
            "rustc",
            f"+{pinned_rust_version}",
            "--version",
        ),
        "cargoVersion": _safe_tool_version(
            root,
            "cargo",
            f"+{pinned_rust_version}",
            "--version",
        ),
        "requiredRustVersion": required_rust_version,
        "nodeVersion": _safe_tool_version(root, "node", "--version"),
        "lockFileSha256": lock_hashes,
    }
    environment["rustVersionMeetsWorkspace"] = (
        required_rust_version == pinned_rust_version == REQUIRED_RUST_VERSION
        and _tool_version_matches_release(
            environment["rustcVersion"],
            tool="rustc",
            required_version=required_rust_version,
        )
        and _tool_version_matches_release(
            environment["cargoVersion"],
            tool="cargo",
            required_version=required_rust_version,
        )
    )
    environment.update(python_environment)
    return environment


def _best_effort_verification_environment(
    root: Path,
) -> dict[str, Any] | None:
    try:
        environment = _verification_environment(root)
    except Exception:  # noqa: BLE001 - retry independent capture for failure evidence.
        return _fallback_verification_environment(root)
    if VERIFICATION_ENVIRONMENT_FIELDS.issubset(environment):
        return environment
    fallback = _fallback_verification_environment(root)
    if fallback is None:
        return None
    fallback.update(environment)
    return fallback


def _append_verification_run(
    evidence: dict[str, Any],
    *,
    result: str,
    protocols: list[str],
    environment: dict[str, Any],
    started_at: str,
    platform_family: str | None = None,
    remote_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = evidence.setdefault("source", {})
    previous_runs = source.setdefault("verificationRuns", [])
    unique_protocols = list(dict.fromkeys(protocols or [GATE_POLICY_PROTOCOL]))
    finished_at = _utc_timestamp()
    run_seed = "\0".join(
        (
            str(source.get("subjectCommit", "")),
            str(source.get("subjectTree", "")),
            started_at,
            finished_at,
            result,
            str(len(previous_runs)),
            *unique_protocols,
        )
    ).encode("utf-8")
    run = {
        "runId": "gate-run:" + hashlib.sha256(run_seed).hexdigest()[:32],
        "subjectCommit": source["subjectCommit"],
        "subjectTree": source["subjectTree"],
        "platformFamily": platform_family or _platform_family(),
        "startedAt": started_at,
        "finishedAt": finished_at,
        "result": result,
        "protocols": unique_protocols,
        "environment": _normalise_environment_v3(environment),
        "remoteProvenance": copy.deepcopy(remote_provenance),
    }
    previous_runs.append(run)
    return run


def _append_failure_run(
    root: Path,
    evidence: dict[str, Any],
    *,
    protocols: list[str],
    started_at: str,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    captured_environment = environment or _best_effort_verification_environment(root)
    if captured_environment is None:
        return None
    return _append_verification_run(
        evidence,
        result="fail",
        protocols=protocols,
        environment=captured_environment,
        started_at=started_at,
    )


def verify_commands(root: Path, evidence: dict[str, Any]) -> bool:
    """Run the full local gate and record each command result."""

    _mark_software_stale(evidence)
    started_at = _utc_timestamp()

    try:
        _validate_repository_python(root)
    except (FileNotFoundError, RuntimeError) as error:
        environment = _best_effort_verification_environment(root)
        item = _software_item(evidence, PYTHON_GATE_PROTOCOL)
        item["result"] = "fail"
        item["details"] = str(error)
        item["verificationMode"] = "not_run"
        item.pop("coveredBy", None)
        item.pop("executedCommand", None)
        _append_failure_run(
            root,
            evidence,
            protocols=[PYTHON_GATE_PROTOCOL],
            environment=environment,
            started_at=started_at,
        )
        _set_verified_worktree_claims(
            evidence,
            verified=False,
            dirty=evidence["source"]["worktreeDirty"],
        )
        return False

    try:
        environment = _verification_environment(root)
    except Exception as error:  # noqa: BLE001 - preflight faults must be recorded.
        environment = _fallback_verification_environment(root)
        item = _software_item(evidence, PYTHON_GATE_PROTOCOL)
        item["result"] = "fail"
        item["details"] = f"verification environment preflight failed: {type(error).__name__}: {error}"
        item["verificationMode"] = "not_run"
        item.pop("coveredBy", None)
        item.pop("executedCommand", None)
        _append_failure_run(
            root,
            evidence,
            protocols=[PYTHON_GATE_PROTOCOL],
            environment=environment,
            started_at=started_at,
        )
        _set_verified_worktree_claims(
            evidence,
            verified=False,
            dirty=evidence["source"]["worktreeDirty"],
        )
        return False
    if environment["pythonLockStatus"] != "match":
        item = _software_item(evidence, PYTHON_GATE_PROTOCOL)
        item["result"] = "fail"
        item["details"] = "repository Python environment differs from poetry.lock: " + "; ".join(
            environment["pythonLockMismatches"]
        )
        item["verificationMode"] = "not_run"
        item.pop("coveredBy", None)
        item.pop("executedCommand", None)
        _append_failure_run(
            root,
            evidence,
            protocols=[PYTHON_GATE_PROTOCOL],
            environment=environment,
            started_at=started_at,
        )
        _set_verified_worktree_claims(
            evidence,
            verified=False,
            dirty=evidence["source"]["worktreeDirty"],
        )
        return False
    if environment["rustVersionMeetsWorkspace"] is not True:
        item = _software_item(evidence, CARGO_FMT_PROTOCOL)
        item["result"] = "fail"
        item["details"] = (
            "Rust toolchain is unavailable, incoherent, or not the exact workspace MSRV "
            f"{environment['requiredRustVersion']}: "
            f"{environment['rustcVersion']}; {environment['cargoVersion']}"
        )
        item["verificationMode"] = "not_run"
        item.pop("coveredBy", None)
        item.pop("executedCommand", None)
        _append_failure_run(
            root,
            evidence,
            protocols=[CARGO_FMT_PROTOCOL],
            environment=environment,
            started_at=started_at,
        )
        _set_verified_worktree_claims(
            evidence,
            verified=False,
            dirty=evidence["source"]["worktreeDirty"],
        )
        return False

    all_passed = True
    executed_protocols: list[str] = []
    for protocol, command_factory, success_details in VERIFICATION_COMMANDS:
        print(f"==> Gate evidence: {protocol}", flush=True)
        executed_protocols.append(protocol)
        item = _software_item(evidence, protocol)
        try:
            command = command_factory(root)
            completed = subprocess.run(command, cwd=root, check=False)
        except Exception as error:  # noqa: BLE001 - command faults are gate failures.
            item["result"] = "fail"
            item["details"] = f"command could not complete: {type(error).__name__}: {error}"
            item["verificationMode"] = "not_run"
            item.pop("coveredBy", None)
            item.pop("executedCommand", None)
            all_passed = False
            break
        if completed.returncode == 0:
            _record_direct_result(
                item,
                command=command,
                passed=True,
                details=success_details,
            )
        else:
            _record_direct_result(
                item,
                command=command,
                passed=False,
                details=f"command exited with {completed.returncode}",
            )
            all_passed = False
            break
    _append_verification_run(
        evidence,
        result="pass" if all_passed else "fail",
        protocols=executed_protocols,
        environment=environment,
        started_at=started_at,
    )
    _set_verified_worktree_claims(
        evidence,
        verified=all_passed,
        dirty=evidence["source"]["worktreeDirty"],
    )
    return all_passed


def _mark_latest_run_failed(evidence: dict[str, Any]) -> bool:
    source = evidence.get("source")
    if not isinstance(source, dict):
        return False
    runs = source.get("verificationRuns")
    if not isinstance(runs, list) or not runs:
        return False
    latest = runs[-1]
    if not isinstance(latest, dict):
        return False
    latest["result"] = "fail"
    return True


def _record_post_verification_failure(
    root: Path,
    evidence: dict[str, Any],
    *,
    reason: str,
    protocol: str,
    started_at: str,
    append_run: bool = True,
    environment: dict[str, Any] | None = None,
    invalidate_software: bool = True,
) -> None:
    _set_gate_blocked(
        evidence,
        reason=reason,
        invalidate_software=invalidate_software,
    )
    if append_run:
        _append_failure_run(
            root,
            evidence,
            protocols=[protocol],
            environment=environment,
            started_at=started_at,
        )


def _write_blocked_after_output_failure(
    root: Path,
    evidence_path: Path,
    evidence: dict[str, Any],
    *,
    error: Exception,
    status_path: Path | None = None,
) -> None:
    """Best-effort authoritative fallback when the paired publication fails."""

    started_at = _utc_timestamp()
    _record_post_verification_failure(
        root,
        evidence,
        reason=(f"generated evidence publication failed: {type(error).__name__}: {error}"),
        protocol=GATE_REFRESH_PROTOCOL,
        started_at=started_at,
    )
    evidence_output = root / evidence_path
    try:
        _atomic_replace_text(
            evidence_output,
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        )
    except OSError:
        # The caller still returns non-zero. No implementation can guarantee a
        # durable transition after the filesystem itself rejects replacement.
        pass
    status_output = root / (
        status_path if status_path is not None else evidence_path.with_name(DEFAULT_STATUS_PATH.name)
    )
    try:
        _atomic_replace_text(status_output, render_status(evidence))
    except OSError:
        # STATUS is derived and must never retain a visible pass after the
        # authoritative evidence has failed closed.
        try:
            status_output.unlink(missing_ok=True)
        except OSError:
            pass


@contextmanager
def verifier_lease(root: Path) -> Any:
    """Hold an exclusive checkout-local lease for the entire publication."""

    # A linked worktree has a .git *file*. Ask Git for this checkout's metadata
    # path rather than treating that file as a directory or sharing another
    # checkout's publication lock.
    metadata_path = _git(root, "rev-parse", "--git-path", VERIFIER_LEASE_PATH.name).rstrip(b"\r\n")
    lease_path = Path(os.fsdecode(metadata_path))
    if not lease_path.is_absolute():
        lease_path = root / lease_path
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            {
                "pid": os.getpid(),
                "startedAt": _utc_timestamp(),
                "purpose": "G0A GateEvidence verification and publication",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    try:
        descriptor = os.open(
            lease_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError as error:
        raise VerifierLeaseError(f"G0A verifier lease is already held: {lease_path}") from error
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        try:
            lease_path.unlink()
        except FileNotFoundError:
            pass


def _generate_locked(
    root: Path = ROOT,
    evidence_path: Path = DEFAULT_EVIDENCE_PATH,
    status_path: Path = DEFAULT_STATUS_PATH,
    *,
    verify: bool = False,
) -> int:
    try:
        evidence = json.loads((root / evidence_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        try:
            (root / status_path).unlink(missing_ok=True)
        except OSError:
            pass
        print(
            f"GateEvidence bootstrap failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1
    refresh_started_at = _utc_timestamp()
    try:
        refreshed, initial_fingerprint = refresh_evidence(root, evidence)
    except Exception as error:  # noqa: BLE001 - stale passes must fail closed.
        if evidence.get("decision") == "passed":
            _record_post_verification_failure(
                root,
                evidence,
                reason=(f"GateEvidence refresh failed: {type(error).__name__}: {error}"),
                protocol=GATE_REFRESH_PROTOCOL,
                started_at=refresh_started_at,
            )
            try:
                write_generated_outputs(
                    root,
                    evidence_path,
                    status_path,
                    evidence,
                )
            except Exception as write_error:  # noqa: BLE001
                _write_blocked_after_output_failure(
                    root,
                    evidence_path,
                    evidence,
                    error=write_error,
                )
            return 1
        try:
            (root / status_path).unlink(missing_ok=True)
        except OSError:
            pass
        print(
            f"GateEvidence refresh failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1

    requested_pass = refreshed.get("decision") == "passed"
    if not verify:
        if requested_pass:
            try:
                validate_passed_decision(refreshed, root=root)
            except Exception as error:  # noqa: BLE001 - persist invalidation first.
                _record_post_verification_failure(
                    root,
                    refreshed,
                    reason=(f"refreshed passed decision is invalid: {type(error).__name__}: {error}"),
                    protocol=GATE_REFRESH_PROTOCOL,
                    started_at=refresh_started_at,
                )
                try:
                    write_generated_outputs(
                        root,
                        evidence_path,
                        status_path,
                        refreshed,
                    )
                except Exception as write_error:  # noqa: BLE001
                    _write_blocked_after_output_failure(
                        root,
                        evidence_path,
                        refreshed,
                        error=write_error,
                    )
                return 1
        try:
            write_generated_outputs(root, evidence_path, status_path, refreshed)
        except Exception as error:  # noqa: BLE001
            if refreshed.get("decision") == "passed":
                _write_blocked_after_output_failure(
                    root,
                    evidence_path,
                    refreshed,
                    error=error,
                )
            return 1
        return 0

    # Persist the fail-closed checkpoint before interpreter, environment, or
    # command preflight. A terminated verifier can therefore never leave the
    # old authoritative pass on disk.
    _set_gate_blocked(
        refreshed,
        reason="local verification is in progress; no passed result is valid",
        invalidate_software=True,
    )
    try:
        write_generated_outputs(root, evidence_path, status_path, refreshed)
    except Exception as error:  # noqa: BLE001
        _write_blocked_after_output_failure(
            root,
            evidence_path,
            refreshed,
            error=error,
        )
        return 1

    if not verify_commands(root, refreshed):
        _set_gate_blocked(
            refreshed,
            reason="the latest local verification run failed",
            invalidate_software=False,
        )
        try:
            write_generated_outputs(root, evidence_path, status_path, refreshed)
        except Exception as error:  # noqa: BLE001
            _write_blocked_after_output_failure(
                root,
                evidence_path,
                refreshed,
                error=error,
                status_path=status_path,
            )
        return 1

    verification_environment = copy.deepcopy(refreshed["source"]["verificationRuns"][-1]["environment"])

    # Publish the passing command details while the decision remains blocked.
    # The post-generation docs check validates this exact derived STATUS before
    # a requested pass can be restored.
    try:
        write_generated_outputs(root, evidence_path, status_path, refreshed)
    except Exception as error:  # noqa: BLE001
        _write_blocked_after_output_failure(
            root,
            evidence_path,
            refreshed,
            error=error,
        )
        return 1

    final_docs_started_at = _utc_timestamp()
    try:
        final_docs_check = subprocess.run(
            [sys.executable, "-I", "scripts/docs_check.py"],
            cwd=root,
            check=False,
        )
    except Exception as error:  # noqa: BLE001 - command launch is a gate failure.
        _record_post_verification_failure(
            root,
            refreshed,
            reason=(f"final generated-document check could not run: {type(error).__name__}: {error}"),
            protocol=FINAL_DOCS_CHECK_PROTOCOL,
            started_at=final_docs_started_at,
            environment=verification_environment,
            invalidate_software=False,
        )
        try:
            write_generated_outputs(root, evidence_path, status_path, refreshed)
        except Exception as write_error:  # noqa: BLE001
            _write_blocked_after_output_failure(
                root,
                evidence_path,
                refreshed,
                error=write_error,
            )
        return 1
    if final_docs_check.returncode != 0:
        _record_post_verification_failure(
            root,
            refreshed,
            reason=(f"final generated-document check failed with exit {final_docs_check.returncode}"),
            protocol=FINAL_DOCS_CHECK_PROTOCOL,
            started_at=final_docs_started_at,
            environment=verification_environment,
            invalidate_software=False,
        )
        try:
            write_generated_outputs(root, evidence_path, status_path, refreshed)
        except Exception as error:  # noqa: BLE001
            _write_blocked_after_output_failure(
                root,
                evidence_path,
                refreshed,
                error=error,
                status_path=status_path,
            )
        return final_docs_check.returncode or 1

    try:
        final_fingerprint = fingerprint_workspace(root)
    except Exception as error:  # noqa: BLE001
        _record_post_verification_failure(
            root,
            refreshed,
            reason=(f"post-verification workspace fingerprint failed: {type(error).__name__}: {error}"),
            protocol=GATE_REFRESH_PROTOCOL,
            started_at=final_docs_started_at,
            environment=verification_environment,
        )
        try:
            write_generated_outputs(root, evidence_path, status_path, refreshed)
        except Exception as write_error:  # noqa: BLE001
            _write_blocked_after_output_failure(
                root,
                evidence_path,
                refreshed,
                error=write_error,
            )
        return 1
    if final_fingerprint != initial_fingerprint:
        _mark_latest_run_failed(refreshed)
        _set_gate_blocked(
            refreshed,
            reason=("HEAD or generated-evidence inputs changed during verification"),
            invalidate_software=True,
        )
        try:
            write_generated_outputs(root, evidence_path, status_path, refreshed)
        except Exception as error:  # noqa: BLE001
            _write_blocked_after_output_failure(
                root,
                evidence_path,
                refreshed,
                error=error,
                status_path=status_path,
            )
        return 1

    _clear_verification_blocker(refreshed)
    if requested_pass:
        _restore_requested_pass(refreshed)
        passing_runs = [
            run
            for run in refreshed["source"].get("verificationRuns", [])
            if isinstance(run, dict) and run.get("result") == "pass"
        ]
        refreshed["decisionDate"] = passing_runs[-1]["finishedAt"][:10]
        try:
            validate_passed_decision(refreshed, root=root)
        except Exception as error:  # noqa: BLE001 - never leave the old pass behind.
            _record_post_verification_failure(
                root,
                refreshed,
                reason=(f"passed-decision validation failed: {type(error).__name__}: {error}"),
                protocol=GATE_POLICY_PROTOCOL,
                started_at=final_docs_started_at,
                environment=verification_environment,
            )
            try:
                write_generated_outputs(
                    root,
                    evidence_path,
                    status_path,
                    refreshed,
                )
            except Exception as write_error:  # noqa: BLE001
                _write_blocked_after_output_failure(
                    root,
                    evidence_path,
                    refreshed,
                    error=write_error,
                )
            return 1
    try:
        prepublish_fingerprint = fingerprint_workspace(root)
    except Exception as error:  # noqa: BLE001
        _record_post_verification_failure(
            root,
            refreshed,
            reason=(f"pre-publication workspace fingerprint failed: {type(error).__name__}: {error}"),
            protocol=GATE_REFRESH_PROTOCOL,
            started_at=final_docs_started_at,
            environment=verification_environment,
        )
        try:
            write_generated_outputs(
                root,
                evidence_path,
                status_path,
                refreshed,
            )
        except Exception as write_error:  # noqa: BLE001
            _write_blocked_after_output_failure(
                root,
                evidence_path,
                refreshed,
                error=write_error,
            )
        return 1
    if prepublish_fingerprint != initial_fingerprint:
        _mark_latest_run_failed(refreshed)
        _set_gate_blocked(
            refreshed,
            reason="HEAD or generated-evidence inputs changed before publication",
            invalidate_software=True,
        )
        try:
            write_generated_outputs(
                root,
                evidence_path,
                status_path,
                refreshed,
            )
        except Exception as error:  # noqa: BLE001
            _write_blocked_after_output_failure(
                root,
                evidence_path,
                refreshed,
                error=error,
                status_path=status_path,
            )
        return 1
    try:
        write_generated_outputs(root, evidence_path, status_path, refreshed)
    except Exception as error:  # noqa: BLE001
        if refreshed.get("decision") == "passed":
            _write_blocked_after_output_failure(
                root,
                evidence_path,
                refreshed,
                error=error,
                status_path=status_path,
            )
        return 1
    try:
        postpublish_fingerprint = fingerprint_workspace(root)
    except Exception as error:  # noqa: BLE001
        _record_post_verification_failure(
            root,
            refreshed,
            reason=(f"post-publication workspace fingerprint failed: {type(error).__name__}: {error}"),
            protocol=GATE_REFRESH_PROTOCOL,
            started_at=final_docs_started_at,
            environment=verification_environment,
        )
        write_generated_outputs(root, evidence_path, status_path, refreshed)
        return 1
    if postpublish_fingerprint != initial_fingerprint:
        _mark_latest_run_failed(refreshed)
        _set_gate_blocked(
            refreshed,
            reason="HEAD or generated-evidence inputs changed during publication",
            invalidate_software=True,
        )
        write_generated_outputs(root, evidence_path, status_path, refreshed)
        return 1
    return 0


def generate(
    root: Path = ROOT,
    evidence_path: Path = DEFAULT_EVIDENCE_PATH,
    status_path: Path = DEFAULT_STATUS_PATH,
    *,
    verify: bool = False,
) -> int:
    """Generate GateEvidence while holding the repository verifier lease."""

    try:
        with verifier_lease(root):
            return _generate_locked(
                root,
                evidence_path,
                status_path,
                verify=verify,
            )
    except VerifierLeaseError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001 - derived STATUS must never stay stale.
        try:
            (root / status_path).unlink(missing_ok=True)
        except OSError:
            pass
        print(
            f"GateEvidence generation failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify",
        action="store_true",
        help="run all local quality gates before recording verification as passing",
    )
    args = parser.parse_args()
    try:
        return generate(verify=args.verify)
    except ValueError as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
