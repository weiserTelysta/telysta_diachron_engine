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
import tomllib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from packaging.markers import Marker, default_environment
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from referencing import Registry, Resource
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_PATH = Path("docs/G0A_GATE_EVIDENCE_2026-07-17.json")
DEFAULT_STATUS_PATH = Path("docs/STATUS.md")
GATE_EVIDENCE_SCHEMA_PATH = Path("docs/GATE_EVIDENCE_MANIFEST_V2.schema.json")
GATE_EVIDENCE_V1_SCHEMA_PATH = Path("docs/GATE_EVIDENCE_MANIFEST_V1.schema.json")
GATE_POLICY_PATH = Path("docs/G0A_POLICY_V1.json")
FINGERPRINT_SCHEMA = "telysta-git-worktree-fingerprint.v2"
GENERATED_PATHS = (DEFAULT_EVIDENCE_PATH, DEFAULT_STATUS_PATH)
REQUIRED_RUST_VERSION = "1.77.2"
PYTHON_LOCK_GROUPS = frozenset({"main", "dev"})
ALLOWED_UNMANAGED_PYTHON_DISTRIBUTIONS = frozenset({"pip", "setuptools", "wheel"})
ADR_EXECUTABLE_CLAIM = (
    "ADR-011 planning evidence is executable and ready for independent review"
)
PLATFORM_REVIEW_CLAIM = (
    "R0A-03 platform and R0A-04 RNG compatibility evidence are ready for "
    "independent review"
)
RNG_VERIFIED_CLAIM = (
    "the current Rust RNG behavior matches the recorded v1 known-answer vectors"
)
WORKTREE_VERIFICATION_CLAIM_SUFFIX = (
    "worktree passes the recorded Python and Rust verification commands"
)
PYTHON_GATE_PROTOCOL = r".\.venv\Scripts\python.exe scripts\check.py"
CARGO_FMT_PROTOCOL = "cargo fmt --all --check"
CARGO_TEST_PROTOCOL = "cargo test --workspace --locked"
CARGO_CLIPPY_PROTOCOL = (
    "cargo clippy --workspace --all-targets --locked -- -D warnings"
)
TARGETED_PYTHON_PROTOCOL = (
    r".\.venv\Scripts\python.exe -m pytest tests\core\test_adr_011_contract.py -q"
)
TARGETED_ADR_RUST_PROTOCOL = (
    "cargo test -p telysta-core --test adr_011_schema_records --locked"
)
TARGETED_RNG_RUST_PROTOCOL = (
    "cargo test -p telysta-core --test rng_known_answers --locked"
)
NODE_PROTOCOL = "node --check apps/desktop/web/app.js"
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
    NODE_PROTOCOL,
)
G0A_REQUIRED_PROTOCOLS = frozenset(G0A_REQUIRED_PROTOCOL_ORDER)
PROTOCOL_PATHS = {
    PYTHON_GATE_PROTOCOL: "scripts/check.py",
    TARGETED_PYTHON_PROTOCOL: "tests/core/test_adr_011_contract.py",
    CARGO_FMT_PROTOCOL: "Cargo.toml",
    CARGO_TEST_PROTOCOL: "Cargo.toml",
    TARGETED_ADR_RUST_PROTOCOL: (
        "crates/telysta-core/tests/adr_011_schema_records.rs"
    ),
    TARGETED_RNG_RUST_PROTOCOL: "crates/telysta-core/tests/rng_known_answers.rs",
    CARGO_CLIPPY_PROTOCOL: "Cargo.toml",
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
        lambda root: [str(repository_python(root)), "scripts/check.py"],
        "required Python and documentation gate passed",
    ),
    (
        TARGETED_PYTHON_PROTOCOL,
        lambda root: [
            str(repository_python(root)),
            "-m",
            "pytest",
            r"tests\core\test_adr_011_contract.py",
            "-q",
        ],
        "targeted ADR-011 Python contract passed directly",
    ),
    (
        CARGO_FMT_PROTOCOL,
        lambda root: ["cargo", "fmt", "--all", "--check"],
        "no formatting differences",
    ),
    (
        CARGO_TEST_PROTOCOL,
        lambda root: ["cargo", "test", "--workspace", "--locked"],
        "Rust workspace tests passed",
    ),
    (
        TARGETED_ADR_RUST_PROTOCOL,
        lambda root: [
            "cargo",
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


def repository_python(root: Path) -> Path:
    """Return the repository-managed Python interpreter for this platform."""

    candidates = (
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "repository Python environment is missing; create .venv before verification"
    )


def _validate_repository_python(root: Path) -> Path:
    expected = repository_python(root)
    actual = Path(sys.executable).resolve()
    if actual != expected:
        raise RuntimeError(
            "gate verification must run from the repository interpreter: "
            f"expected {expected}, got {actual}"
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
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _schema_errors(
    evidence: dict[str, Any],
    *,
    root: Path = ROOT,
) -> list[str]:
    schema = json.loads((root / GATE_EVIDENCE_SCHEMA_PATH).read_text(encoding="utf-8"))
    v1_schema = json.loads(
        (root / GATE_EVIDENCE_V1_SCHEMA_PATH).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator.check_schema(v1_schema)
    registry = Registry().with_resource(
        v1_schema["$id"],
        Resource.from_contents(v1_schema),
    )
    validator = Draft202012Validator(schema, registry=registry)
    errors: list[str] = []
    for error in sorted(
        validator.iter_errors(evidence),
        key=lambda item: ".".join(str(part) for part in item.absolute_path),
    ):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


def validate_gate_evidence_manifest(
    evidence: dict[str, Any],
    *,
    root: Path = ROOT,
    now: datetime | None = None,
) -> None:
    """Validate the closed G0A manifest contract before interpreting a decision."""

    issues = _schema_errors(evidence, root=root)

    requirements = evidence.get("requirements")
    if isinstance(requirements, list):
        requirement_ids = [
            item.get("id") for item in requirements if isinstance(item, dict)
        ]
        if len(requirement_ids) != len(set(requirement_ids)):
            issues.append("requirements contain duplicate IDs")
        if set(requirement_ids) != G0A_REQUIRED_REQUIREMENT_IDS:
            missing = sorted(G0A_REQUIRED_REQUIREMENT_IDS - set(requirement_ids))
            unexpected = sorted(set(requirement_ids) - G0A_REQUIRED_REQUIREMENT_IDS)
            issues.append(
                "G0A requirement IDs differ from the contract"
                f"; missing={missing}; unexpected={unexpected}"
            )

    evidence_items = evidence.get("evidence")
    if isinstance(evidence_items, list):
        kinds = {
            item.get("kind") for item in evidence_items if isinstance(item, dict)
        }
        missing_kinds = sorted(G0A_REQUIRED_EVIDENCE_KINDS - kinds)
        if missing_kinds:
            issues.append(
                "G0A evidence kinds are missing: " + ", ".join(missing_kinds)
            )
        protocols = [
            item.get("protocol")
            for item in evidence_items
            if isinstance(item, dict)
            and item.get("kind") == "SoftwareVerificationEvidence"
        ]
        if len(protocols) != len(set(protocols)):
            issues.append("software evidence contains duplicate protocols")
        protocol_set = {protocol for protocol in protocols if isinstance(protocol, str)}
        if protocol_set != G0A_REQUIRED_PROTOCOLS:
            missing = sorted(G0A_REQUIRED_PROTOCOLS - protocol_set)
            unexpected = sorted(protocol_set - G0A_REQUIRED_PROTOCOLS)
            issues.append(
                "G0A verification protocols differ from the contract"
                f"; missing={missing}; unexpected={unexpected}"
            )

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
        run
        for run in source.get("verificationRuns", [])
        if isinstance(run, dict) and run.get("result") == "pass"
    ]
    for run in passing_runs:
        recorded = run.get("environment", {}).get("lockFileSha256")
        if recorded != subject_lock_hashes:
            issues.append(
                f"verification lock-file hashes differ from subject: {run.get('runId')}"
            )
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
    untracked = sorted(
        path.decode("utf-8", errors="surrogateescape")
        for path in untracked_raw.split(b"\0")
        if path
    )
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
            "kind": "SoftwareVerificationEvidence",
            "path": path,
            "protocol": protocol,
            "result": "not_run_for_fingerprint",
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
        or item.get("protocol") in G0A_REQUIRED_PROTOCOLS
    ]
    for protocol in G0A_REQUIRED_PROTOCOL_ORDER:
        _software_item(evidence, protocol)


def _mark_software_stale(evidence: dict[str, Any]) -> None:
    for item in evidence.get("evidence", []):
        if item.get("kind") != "SoftwareVerificationEvidence":
            continue
        item["result"] = "not_run_for_fingerprint"
        item["details"] = "verification must be rerun for the recorded worktree fingerprint"
        item["verificationMode"] = "not_run"
        item.pop("coveredBy", None)
        item.pop("executedCommand", None)


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
    requirement = next(
        item for item in evidence["requirements"] if item["id"] == "R0A-05"
    )
    if fingerprint.dirty:
        requirement["status"] = "failed"
        requirement["reason"] = (
            "the generated-evidence inputs contain "
            f"{fingerprint.status_entry_count} modified or untracked entries; "
            "HEAD does not contain the reviewed Rust/Tauri/doc baseline"
        )
    else:
        requirement["status"] = "ready_for_independent_review"
        requirement["reason"] = (
            "the worktree is clean; independent clean-checkout reproduction is still required"
        )


def _migrate_manifest_v2(evidence: dict[str, Any]) -> bool:
    """Migrate a legacy manifest conservatively; passing state never carries over."""

    if evidence.get("schemaVersion") == "telysta-gate-evidence-manifest.v2":
        return False
    was_passed = evidence.get("decision") == "passed"
    evidence["$schema"] = GATE_EVIDENCE_SCHEMA_PATH.name
    evidence["schemaVersion"] = "telysta-gate-evidence-manifest.v2"
    evidence["decision"] = "blocked"
    allowed = evidence.setdefault("claims", {}).setdefault("allowed", [])
    forbidden = evidence["claims"].setdefault("forbidden", [])
    if "G0A has passed" in allowed:
        allowed.remove("G0A has passed")
    if "G0A has passed" not in forbidden:
        forbidden.append("G0A has passed")
    if was_passed and not any(
        item.get("id") == "G0A-B99" for item in evidence.get("blockers", [])
    ):
        evidence.setdefault("blockers", []).append(
            {
                "severity": "blocking",
                "id": "G0A-B99",
                "summary": "v1 evidence must be independently re-verified under v2",
            }
        )
    return True


def refresh_evidence(
    root: Path,
    evidence: dict[str, Any],
) -> tuple[dict[str, Any], WorkspaceFingerprint]:
    """Refresh generated fields without claiming that quality commands passed."""

    refreshed = copy.deepcopy(evidence)
    migrated = _migrate_manifest_v2(refreshed)
    _synchronize_required_software_items(refreshed)
    fingerprint = fingerprint_workspace(root)
    previous_source = refreshed.get("source", {})
    previous_sha = previous_source.get("worktreeInventorySha256")
    previous_subject = previous_source.get("subjectCommit")
    previous_tree = previous_source.get("subjectTree")
    retain_attested_subject = (
        refreshed.get("decision") == "passed"
        and isinstance(previous_subject, str)
        and isinstance(previous_tree, str)
    )
    subject_commit = (
        previous_subject if retain_attested_subject else fingerprint.base_commit
    )
    subject_tree = (
        previous_tree
        if retain_attested_subject
        else _commit_tree(root, fingerprint.base_commit)
    )
    source = {
        "subjectCommit": subject_commit,
        "subjectTree": subject_tree,
        "worktreeDirty": fingerprint.dirty,
        "worktreeStatusEntryCount": fingerprint.status_entry_count,
        "worktreeFingerprintSchema": FINGERPRINT_SCHEMA,
        "worktreeInventorySha256": fingerprint.sha256,
        "excludedGeneratedPaths": [path.as_posix() for path in GENERATED_PATHS],
        "environment": previous_source.get("environment", "local workspace"),
    }
    same_subject = (
        previous_subject == subject_commit and previous_tree == subject_tree
    )
    if previous_sha == fingerprint.sha256 and same_subject and not migrated:
        existing_runs = previous_source.get("verificationRuns")
        if existing_runs:
            source["verificationRuns"] = existing_runs
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
    requirement_by_id = {
        item.get("id"): item
        for item in evidence.get("requirements", [])
        if isinstance(item, dict)
    }
    evidence_by_key = {
        (item.get("path"), item.get("kind")): item
        for item in evidence.get("evidence", [])
        if isinstance(item, dict)
    }
    non_waivable = set(policy.get("nonWaivableRequirementIds", []))
    for requirement_id, rule in policy.get("requirements", {}).items():
        requirement = requirement_by_id.get(requirement_id)
        if requirement is None:
            issues.append(f"gate policy requirement is missing: {requirement_id}")
            continue
        if requirement.get("status") == "waived" and requirement_id in non_waivable:
            issues.append(f"requirement is not waivable: {requirement_id}")
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
                issues.append(
                    f"{requirement_id} lacks evidence "
                    f"{expected['kind']}:{expected['path']}"
                )
                continue
            accepted_results = set(expected["acceptedResults"])
            if item.get("result") not in accepted_results:
                issues.append(
                    f"{requirement_id} evidence {expected['path']} has result "
                    f"{item.get('result')!r}; expected one of {sorted(accepted_results)}"
                )
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
        changed = {
            item.decode("utf-8", errors="surrogateescape")
            for item in changed_raw.split(b"\0")
            if item
        }
        allowed = {path.as_posix() for path in GENERATED_PATHS}
        unexpected = sorted(changed - allowed)
        if unexpected:
            issues.append(
                "attestation revision changes non-generated paths: "
                + ", ".join(unexpected)
            )

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

    issues: list[str] = []
    requirements = evidence.get("requirements", [])
    requirement_by_id = {
        item.get("id"): item for item in requirements if isinstance(item, dict)
    }
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
            issues.append(
                "waiver is missing required fields: " + ", ".join(sorted(missing))
            )
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
        str(item.get("id"))
        for item in requirements
        if isinstance(item, dict) and item.get("status") == "waived"
    }
    missing_waivers = sorted(waived_requirements - waiver_requirement_ids)
    if missing_waivers:
        issues.append(
            "waived requirements lack registered waivers: " + ", ".join(missing_waivers)
        )

    software_items = [
        item
        for item in evidence.get("evidence", [])
        if isinstance(item, dict)
        and item.get("kind") == "SoftwareVerificationEvidence"
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
            if not isinstance(item.get("executedCommand"), str) or not item[
                "executedCommand"
            ].strip():
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
            reviewer_roles.update(
                role
                for role in reviewer.get("roles", [])
                if isinstance(role, str)
            )
            account_id = _identity_account_id(reviewer)
            if account_id:
                if account_id in reviewer_account_ids:
                    issues.append("duplicate reviewer stable account ID")
                reviewer_account_ids.add(account_id)
            if reviewer.get("reviewedSubjectCommit") != evidence.get("source", {}).get(
                "subjectCommit"
            ):
                issues.append("reviewer attestation targets a different subject commit")
            if reviewer.get("reviewedSubjectTree") != evidence.get("source", {}).get(
                "subjectTree"
            ):
                issues.append("reviewer attestation targets a different subject tree")
            if reviewer.get("decision") != "accepted":
                issues.append("reviewer attestation is not accepted")
            if reviewer.get("conflictOfInterest") is not False:
                issues.append("reviewer conflict-of-interest declaration is not clear")
        missing_roles = {"architecture", "migration"} - reviewer_roles
        if missing_roles:
            issues.append(
                "independent reviewer roles are missing: "
                + ", ".join(sorted(missing_roles))
            )
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
        passing_runs = [
            run
            for run in source.get("verificationRuns", [])
            if isinstance(run, dict) and run.get("result") == "pass"
        ]
        if not passing_runs:
            issues.append("passing verification run is missing")
        for run in passing_runs:
            protocols = run.get("protocols")
            if not isinstance(protocols, list) or set(protocols) != G0A_REQUIRED_PROTOCOLS:
                issues.append(
                    f"verification run protocols are incomplete: {run.get('runId')}"
                )
            environment = run.get("environment")
            if not isinstance(environment, dict):
                issues.append(
                    f"verification run environment is missing: {run.get('runId')}"
                )
                continue
            missing_environment = sorted(
                VERIFICATION_ENVIRONMENT_FIELDS - environment.keys()
            )
            if missing_environment:
                issues.append(
                    "verification environment lacks: "
                    + ", ".join(missing_environment)
                )
            lock_hashes = environment.get("lockFileSha256")
            if not isinstance(lock_hashes, dict) or set(lock_hashes) != {
                path.as_posix() for path in LOCK_FILES
            }:
                issues.append("verification lock-file hashes are incomplete")
            elif any(not _is_sha256(value) for value in lock_hashes.values()):
                issues.append("verification lock-file hashes are invalid")
            string_fields = {
                "platform",
                "pythonExecutable",
                "pythonVersion",
                "pythonInstalledDistributionsSha256",
                "rustcVersion",
                "cargoVersion",
                "requiredRustVersion",
                "nodeVersion",
            }
            for field in string_fields:
                if not isinstance(environment.get(field), str) or not environment[
                    field
                ].strip():
                    issues.append(f"verification environment field is invalid: {field}")
            if environment.get("pythonLockStatus") != "match":
                issues.append("Python environment does not match poetry.lock")
            if environment.get("pythonLockMismatches") != []:
                issues.append("Python lock mismatches remain")
            if environment.get("requiredRustVersion") != REQUIRED_RUST_VERSION:
                issues.append("required Rust version differs from the workspace contract")
            if environment.get("rustVersionMeetsWorkspace") is not True:
                issues.append("Rust toolchain is older than the workspace MSRV")
        if passing_runs:
            latest = max(str(run["finishedAt"]) for run in passing_runs)
            if evidence.get("decisionDate") != latest[:10]:
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
    finished_runs = [
        str(run["finishedAt"])
        for run in source.get("verificationRuns", [])
        if isinstance(run, dict) and run.get("result") == "pass"
    ]
    verified_at = max(finished_runs) if finished_runs else "not-verified"
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
    lines.extend(
        f"| {item['id']} | `{item['status']}` | {item['name']} |"
        for item in evidence["requirements"]
    )
    lines.extend(["", "## 当前允许声明", ""])
    lines.extend(f"- {claim}" for claim in evidence["claims"]["allowed"])
    lines.extend(["", "## 当前禁止声明", ""])
    lines.extend(f"- {claim}" for claim in evidence["claims"]["forbidden"])
    lines.extend(["", "## Blockers", ""])
    lines.extend(
        f"- `{item['id']}`：{item['summary']}" for item in evidence["blockers"]
    )
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
    evidence_output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    status_output.write_text(render_status(evidence), encoding="utf-8")


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
            if isinstance(group_marker, str) and Marker(group_marker).evaluate(
                environment
            ):
                return True
        return False
    raise ValueError(f"unsupported poetry.lock marker shape: {marker_spec!r}")


def _locked_python_distributions(root: Path) -> dict[str, str]:
    lock = tomllib.loads((root / "poetry.lock").read_text(encoding="utf-8"))
    expected: dict[str, str] = {}
    for package in lock.get("package", []):
        groups = set(package.get("groups", ["main"]))
        selected_groups = groups & PYTHON_LOCK_GROUPS
        if not selected_groups or not _marker_applies(
            package.get("markers"), selected_groups
        ):
            continue
        name = canonicalize_name(package["name"])
        version = str(package["version"])
        previous = expected.get(name)
        if previous is not None and previous != version:
            raise ValueError(
                f"poetry.lock selects multiple versions for {name}: "
                f"{previous}, {version}"
            )
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
        name: version
        for name, version in installed.items()
        if name not in ALLOWED_UNMANAGED_PYTHON_DISTRIBUTIONS
    }
    mismatches: list[str] = []
    for name in sorted(expected.keys() - compared_installed.keys()):
        mismatches.append(f"missing {name}=={expected[name]}")
    for name in sorted(compared_installed.keys() - expected.keys()):
        mismatches.append(f"unexpected {name}=={compared_installed[name]}")
    for name in sorted(expected.keys() & compared_installed.keys()):
        if expected[name] != compared_installed[name]:
            mismatches.append(
                f"version {name}: locked {expected[name]}, "
                f"installed {compared_installed[name]}"
            )
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


def _rust_version_meets_workspace(
    rustc_output: str,
    required_version: str,
) -> bool:
    if not rustc_output.startswith("rustc "):
        return False
    try:
        actual = Version(rustc_output.split()[1])
        required = Version(required_version)
    except (IndexError, InvalidVersion):
        return False
    return actual >= required


def _verification_environment(root: Path) -> dict[str, Any]:
    required_rust_version = _workspace_rust_version(root)
    rustc_version = _tool_version(root, "rustc", "--version")
    cargo_version = _tool_version(root, "cargo", "--version")
    environment = {
        "platform": platform.platform(),
        "pythonExecutable": str(Path(sys.executable).resolve()),
        "pythonVersion": platform.python_version(),
        "rustcVersion": rustc_version,
        "cargoVersion": cargo_version,
        "requiredRustVersion": required_rust_version,
        "rustVersionMeetsWorkspace": (
            required_rust_version == REQUIRED_RUST_VERSION
            and _rust_version_meets_workspace(
                rustc_version,
                required_rust_version,
            )
            and not cargo_version.startswith("unavailable")
        ),
        "nodeVersion": _tool_version(root, "node", "--version"),
        "lockFileSha256": _lock_file_hashes(root),
    }
    environment.update(_python_environment_evidence(root))
    return environment


def verify_commands(root: Path, evidence: dict[str, Any]) -> bool:
    """Run the full local gate and record each command result."""

    _mark_software_stale(evidence)
    previous_runs = list(evidence["source"].get("verificationRuns", []))

    try:
        _validate_repository_python(root)
    except (FileNotFoundError, RuntimeError) as error:
        item = _software_item(evidence, PYTHON_GATE_PROTOCOL)
        item["result"] = "fail"
        item["details"] = str(error)
        item["verificationMode"] = "not_run"
        _set_verified_worktree_claims(
            evidence,
            verified=False,
            dirty=evidence["source"]["worktreeDirty"],
        )
        return False

    started_at = _utc_timestamp()
    environment = _verification_environment(root)
    if environment["pythonLockStatus"] != "match":
        item = _software_item(evidence, PYTHON_GATE_PROTOCOL)
        item["result"] = "fail"
        item["details"] = (
            "repository Python environment differs from poetry.lock: "
            + "; ".join(environment["pythonLockMismatches"])
        )
        item["verificationMode"] = "not_run"
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
            "Rust toolchain is unavailable or older than workspace MSRV "
            f"{environment['requiredRustVersion']}: "
            f"{environment['rustcVersion']}; {environment['cargoVersion']}"
        )
        item["verificationMode"] = "not_run"
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
        command = command_factory(root)
        completed = subprocess.run(command, cwd=root, check=False)
        executed_protocols.append(protocol)
        item = _software_item(evidence, protocol)
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
    finished_at = _utc_timestamp()
    run_seed = (
        evidence["source"]["subjectCommit"]
        + evidence["source"]["subjectTree"]
        + started_at
        + finished_at
    ).encode("utf-8")
    previous_runs.append(
        {
            "runId": "gate-run:" + hashlib.sha256(run_seed).hexdigest()[:32],
            "subjectCommit": evidence["source"]["subjectCommit"],
            "subjectTree": evidence["source"]["subjectTree"],
            "startedAt": started_at,
            "finishedAt": finished_at,
            "result": "pass" if all_passed else "fail",
            "protocols": executed_protocols,
            "environment": environment,
        }
    )
    evidence["source"]["verificationRuns"] = previous_runs
    _set_verified_worktree_claims(
        evidence,
        verified=all_passed,
        dirty=evidence["source"]["worktreeDirty"],
    )
    return all_passed


def generate(
    root: Path = ROOT,
    evidence_path: Path = DEFAULT_EVIDENCE_PATH,
    status_path: Path = DEFAULT_STATUS_PATH,
    *,
    verify: bool = False,
) -> int:
    evidence = json.loads((root / evidence_path).read_text(encoding="utf-8"))
    refreshed, _ = refresh_evidence(root, evidence)
    validate_passed_decision(refreshed, root=root)
    write_generated_outputs(root, evidence_path, status_path, refreshed)

    if verify:
        if not verify_commands(root, refreshed):
            validate_passed_decision(refreshed, root=root)
            write_generated_outputs(root, evidence_path, status_path, refreshed)
            return 1
        passing_runs = refreshed["source"]["verificationRuns"]
        refreshed["decisionDate"] = passing_runs[-1]["finishedAt"][:10]
        validate_passed_decision(refreshed, root=root)
        write_generated_outputs(root, evidence_path, status_path, refreshed)
        final_docs_check = subprocess.run(
            [sys.executable, "scripts/docs_check.py"],
            cwd=root,
            check=False,
        )
        if final_docs_check.returncode != 0:
            return final_docs_check.returncode
    else:
        validate_passed_decision(refreshed, root=root)
    return 0


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
