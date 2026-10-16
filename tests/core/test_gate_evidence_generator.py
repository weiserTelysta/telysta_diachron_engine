"""Evidence generation must be reproducible and must not self-reference."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility.
    import tomli as tomllib

import scripts.generate_gate_evidence as gate_evidence
from scripts.generate_gate_evidence import (
    ADR_EXECUTABLE_CLAIM,
    DELIVERY_READINESS_SCHEMA_VERSION,
    FINGERPRINT_SCHEMA,
    G0A_REQUIRED_DELIVERY_WORK_PACKAGE_IDS,
    G0A_REQUIRED_PROTOCOL_ORDER,
    G0A_REQUIRED_REQUIREMENT_IDS,
    PLATFORM_REVIEW_CLAIM,
    REQUIRED_RUST_VERSION,
    RNG_VERIFIED_CLAIM,
    TARGETED_RNG_RUST_PROTOCOL,
    WORKTREE_VERIFICATION_CLAIM_SUFFIX,
    _set_verified_worktree_claims,
    _subject_attestation_issues,
    _subject_content_issues,
    _gate_policy_issues,
    _validated_verified_at,
    fingerprint_workspace,
    refresh_evidence,
    validate_gate_evidence_manifest,
    validate_passed_decision,
    verify_commands,
    write_generated_outputs,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("baseline\n", encoding="utf-8")
    for relative in (
        gate_evidence.GATE_EVIDENCE_V1_SCHEMA_PATH,
        gate_evidence.GATE_EVIDENCE_V2_SCHEMA_PATH,
        gate_evidence.GATE_EVIDENCE_SCHEMA_PATH,
        gate_evidence.GATE_POLICY_SCHEMA_PATH,
        gate_evidence.GATE_POLICY_PATH,
        Path("docs/governance/GATE_EVIDENCE_MODEL_V3.md"),
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((gate_evidence.ROOT / relative).read_bytes())
    _git(tmp_path, "add", "README.md", "docs")
    _git(tmp_path, "commit", "-m", "baseline")
    return tmp_path


def test_execution_lock_hashes_use_workspace_bytes_not_head(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    for relative in gate_evidence.LOCK_FILES:
        (root / relative).write_bytes(b"committed lock\n")
    _git(root, "add", "Cargo.lock", "poetry.lock")
    _git(root, "commit", "-m", "add input locks")
    (root / "poetry.lock").write_bytes(b"actual uncommitted input\n")

    assert gate_evidence._lock_file_hashes(root) == {
        "Cargo.lock": hashlib.sha256(b"committed lock\n").hexdigest(),
        "poetry.lock": hashlib.sha256(b"actual uncommitted input\n").hexdigest(),
    }


def test_execution_lock_missing_from_workspace_does_not_fall_back_to_head(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    for relative in gate_evidence.LOCK_FILES:
        (root / relative).write_bytes(b"committed lock\n")
    _git(root, "add", "Cargo.lock", "poetry.lock")
    _git(root, "commit", "-m", "add input locks")
    (root / "poetry.lock").unlink()

    with pytest.raises(FileNotFoundError, match="poetry.lock"):
        gate_evidence._lock_file_hashes(root)


@pytest.mark.parametrize("failure", [None, "final-docs", "publication", "source-change"])
def test_local_capture_includes_final_docs_and_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None,
) -> None:
    root = _repository(tmp_path)
    (root / ".gitignore").write_text("target/\n", encoding="utf-8")
    for relative in gate_evidence.LOCK_FILES:
        (root / relative).write_bytes(b"test lock\n")
    (root / "scripts").mkdir()
    (root / "scripts/docs_check.py").write_text(
        "raise SystemExit(7)\n" if failure == "final-docs" else "print('final-docs-output')\n",
        encoding="utf-8",
    )
    _git(root, "add", ".gitignore", "Cargo.lock", "poetry.lock", "scripts")
    _git(root, "commit", "-m", "add local verifier inputs")
    evidence_path, status_path = _write_gate_outputs(root, _evidence())
    commands = ((gate_evidence.PYTHON_GATE_PROTOCOL,
                 lambda _: [sys.executable, "-I", "-c", "print('primary-output')"], "test command"),)
    monkeypatch.setattr(gate_evidence, "VERIFICATION_COMMANDS", commands)

    def passing_commands(root_arg, candidate, recorder):
        environment = {key: "test" for key in gate_evidence.VERIFICATION_ENVIRONMENT_FIELDS}
        environment.update(
            lockFileSha256=gate_evidence._lock_file_hashes(root_arg),
            pythonLockStatus="match", pythonLockMismatches=[], rustVersionMeetsWorkspace=True,
            pythonInstalledDistributionsSha256="e" * 64, pythonExecutable=sys.executable,
            requiredRustVersion=gate_evidence.REQUIRED_RUST_VERSION,
            rustcVersion="rustc 1.88.0 (test)", cargoVersion="cargo 1.88.0 (test)",
        )
        recorder.environment(environment)
        assert gate_evidence._run_command(root_arg, commands[0][0], commands[0][1](root_arg), recorder).returncode == 0
        _append_test_run(candidate, result="pass")
        if failure == "source-change":
            (root_arg / "README.md").write_text("changed while running\n", encoding="utf-8")
        return True

    monkeypatch.setattr(gate_evidence, "verify_commands", passing_commands)
    if failure == "publication":
        real_write = gate_evidence.write_generated_outputs
        calls = 0
        def write(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("test final publication failure")
            return real_write(*args, **kwargs)
        monkeypatch.setattr(gate_evidence, "write_generated_outputs", write)
    result = gate_evidence.generate(
        root, evidence_path.relative_to(root), status_path.relative_to(root),
        verify=True, record_local=True,
    )
    bundle_path, = (root / "target/local-verification").glob("run-*")
    bundle = json.loads((bundle_path / "manifest.json").read_text(encoding="utf-8"))
    assert result == (0 if failure is None else (7 if failure == "final-docs" else 1))
    assert bundle["result"] == ("passed" if failure is None else "failed")
    assert len(bundle["commands"]) == 2
    assert (bundle_path / "00.log").read_bytes().strip() == b"primary-output"
    assert bundle["commands"][-1]["protocol"] == gate_evidence.FINAL_DOCS_CHECK_PROTOCOL
    persisted = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert persisted["decision"] == "blocked"
    if failure is None:
        assert (bundle_path / "01.log").read_bytes().strip() == b"final-docs-output"
        assert gate_evidence.check_bundle(
            bundle_path, gate_evidence._local_command_plan(root), gate_evidence._local_source_snapshot(root),
            root, gate_evidence.VERIFICATION_ENVIRONMENT_FIELDS,
        )["result"] == "passed"
        for field, invalid in (
            ("pythonInstalledDistributionsSha256", "not-a-sha256"),
            ("pythonInstalledDistributionsSha256", "e" * 64 + "\n"),
            ("rustcVersion", "rustc 1.99.0"), ("cargoVersion", "cargo 1.99.0"),
            ("requiredRustVersion", "1.99.0"), ("pythonExecutable", "/wrong/python"),
        ):
            altered = json.loads(json.dumps(bundle))
            altered["environment"][field] = invalid
            (bundle_path / "manifest.json").write_text(json.dumps(altered), encoding="utf-8")
            with pytest.raises(ValueError):
                gate_evidence._check_local_bundle(root, bundle_path)


def test_local_capture_rejects_dirty_source_without_creating_bundle(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    for relative in gate_evidence.LOCK_FILES:
        (root / relative).write_bytes(b"uncommitted lock\n")
    assert gate_evidence.generate(root, verify=True, record_local=True) == 1
    assert not (root / "target/local-verification").exists()


@pytest.fixture
def ignore_gate_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    # Unit fixtures below test structural predicates with synthetic accounts
    # and provider records. They cannot establish external attestation trust.
    monkeypatch.setattr(gate_evidence, "_gate_policy_issues", lambda evidence, root: [])
    monkeypatch.setattr(gate_evidence, "_trusted_attestation_issues", lambda evidence, root: [])


def _fixture_sha256(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def test_structured_claims_cannot_replace_external_attestation_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Isolate the external trust boundary; this fixture has every required
    # structural field but supplies no authenticated accounts/provider results
    # or independently validated terminal payloads.
    monkeypatch.setattr(gate_evidence, "_gate_policy_issues", lambda evidence, root: [])
    with pytest.raises(ValueError, match="external attestation verification is unavailable"):
        validate_passed_decision(_passing_evidence(), verify_current_workspace=False)


def _account(account_id: str, *, role: str) -> dict[str, str]:
    return {
        "provider": "test",
        "stableAccountId": f"account:{account_id}",
        "login": account_id,
        "displayName": account_id.replace("-", " ").title(),
        "role": role,
    }


def _remote_provenance(run_suffix: str) -> dict[str, str]:
    return {
        "provider": "test-ci",
        "repository": "example/telysta",
        "workflow": "g0a",
        "runId": f"remote-run:{run_suffix}",
        "jobId": f"remote-job:{run_suffix}",
        "url": f"https://example.invalid/actions/runs/{run_suffix}",
        "artifactSha256": _fixture_sha256(f"artifact:{run_suffix}"),
    }


def _verification_environment(platform_family: str) -> dict[str, Any]:
    return {
        "os": "Windows 11" if platform_family == "windows" else "Ubuntu 24.04",
        "architecture": "x86_64",
        "toolchain": {
            "python": "Python 3.13.5",
            "rustc": f"rustc {REQUIRED_RUST_VERSION} (test)",
            "cargo": f"cargo {REQUIRED_RUST_VERSION} (test)",
            "node": "v24.0.0",
        },
        "lockFileSha256": {
            "Cargo.lock": _fixture_sha256("Cargo.lock"),
            "poetry.lock": _fixture_sha256("poetry.lock"),
        },
    }


def _verification_run(
    platform_family: str,
    run_suffix: str,
    *,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    return {
        "runId": f"gate-run:{run_suffix * 32}",
        "subjectCommit": "a" * 40,
        "subjectTree": "b" * 40,
        "platformFamily": platform_family,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "result": "pass",
        "protocols": list(G0A_REQUIRED_PROTOCOL_ORDER),
        "environment": _verification_environment(platform_family),
        "remoteProvenance": _remote_provenance(run_suffix),
    }


def _terminal_evidence(
    requirement_id: str,
    *,
    result: str = "pending",
) -> tuple[dict[str, Any], dict[str, Any]]:
    kind_by_requirement = {
        "R0A-05": "RepositoryBaselineEvidence",
        "R0A-07": "DeliveryReadinessEvidence",
        "R0A-08": "SoftwareVerificationEvidence",
        "R0A-09": "AuthorityIntegrityEvidence",
        "R0A-10": "LegacyContainmentEvidence",
    }
    evidence_id = f"terminal:{requirement_id.lower()}"
    sha256 = _fixture_sha256(evidence_id)
    item = {
        "evidenceId": evidence_id,
        "kind": kind_by_requirement[requirement_id],
        "path": "README.md",
        "sha256": sha256,
        "result": result,
    }
    terminal = {
        "evidenceId": evidence_id,
        "path": item["path"],
        "kind": item["kind"],
        "result": result,
        "sha256": sha256,
    }
    return item, terminal


def _waiver(requirement_id: str, *, expires_at: str) -> dict[str, Any]:
    return {
        "requirementId": requirement_id,
        "status": "active",
        "requestedBy": _account("requester", role="waiver-requester"),
        "approvedBy": _account("waiver-reviewer", role="waiver-approver"),
        "reason": "temporary test waiver",
        "createdAt": "2026-07-16T00:00:00Z",
        "expiresAt": expires_at,
    }


def _evidence() -> dict[str, Any]:
    software = [
        {
            "evidenceId": f"software:{index:02d}",
            "kind": "SoftwareVerificationEvidence",
            "path": "README.md",
            "sha256": _fixture_sha256(f"software:{index:02d}"),
            "protocol": protocol,
            "result": "pass",
            "details": "old result",
            "verificationMode": "direct",
            "executedCommand": protocol,
        }
        for index, protocol in enumerate(G0A_REQUIRED_PROTOCOL_ORDER)
    ]
    other_evidence = [
        {
            "evidenceId": f"contract:{index:02d}",
            "kind": kind,
            "path": "README.md",
            "sha256": _fixture_sha256(f"contract:{index:02d}"),
            "result": "pass",
        }
        for index, kind in enumerate(
            (
                "ArchitectureContractEvidence",
                "ArchitectureDecisionEvidence",
                "DeterminismEvidence",
            )
        )
    ]
    terminal_pairs = {
        requirement_id: _terminal_evidence(requirement_id)
        for requirement_id in ("R0A-05", "R0A-07", "R0A-08", "R0A-09", "R0A-10")
    }
    terminal_items = [pair[0] for pair in terminal_pairs.values()]
    evidence_items = software + other_evidence + terminal_items
    default_evidence_id = software[0]["evidenceId"]
    policy_payload = (gate_evidence.ROOT / gate_evidence.GATE_POLICY_PATH).read_bytes()
    return {
        "$schema": gate_evidence.GATE_EVIDENCE_SCHEMA_PATH.name,
        "schemaVersion": gate_evidence.GATE_EVIDENCE_SCHEMA_VERSION,
        "gateId": "G0A",
        "gateName": "test",
        "decision": "blocked",
        "decisionDate": "2026-07-17",
        "source": {
            "subjectCommit": "a" * 40,
            "subjectTree": "b" * 40,
            "worktreeDirty": False,
            "worktreeStatusEntryCount": 0,
            "worktreeFingerprintSchema": FINGERPRINT_SCHEMA,
            "worktreeInventorySha256": _fixture_sha256("worktree"),
            "excludedGeneratedPaths": [
                "docs/G0A_GATE_EVIDENCE_2026-07-17.json",
                "docs/STATUS.md",
            ],
            "verificationRuns": [],
        },
        "gatePolicy": {
            "path": gate_evidence.GATE_POLICY_PATH.as_posix(),
            "schemaVersion": gate_evidence.GATE_POLICY_SCHEMA_VERSION,
            "sha256": hashlib.sha256(policy_payload).hexdigest(),
        },
        "claims": {
            "allowed": [
                ADR_EXECUTABLE_CLAIM,
                PLATFORM_REVIEW_CLAIM,
                RNG_VERIFIED_CLAIM,
                (f"the recorded dirty {WORKTREE_VERIFICATION_CLAIM_SUFFIX}"),
            ],
            "forbidden": ["G0A has passed"],
        },
        "evidence": evidence_items,
        "requirements": [
            {
                "id": requirement_id,
                "name": f"requirement {requirement_id}",
                "status": "failed",
                "evidenceRefs": [
                    (
                        terminal_pairs[requirement_id][0]["evidenceId"]
                        if requirement_id in terminal_pairs
                        else default_evidence_id
                    )
                ],
                "terminalEvidence": (terminal_pairs[requirement_id][1] if requirement_id in terminal_pairs else None),
            }
            for requirement_id in sorted(G0A_REQUIRED_REQUIREMENT_IDS)
        ],
        "blockers": [{"severity": "blocking", "id": "G0A-B01", "summary": "blocked"}],
        "owner": None,
        "reviewers": [],
        "deliveryReadiness": {
            "schemaVersion": DELIVERY_READINESS_SCHEMA_VERSION,
            "workPackages": [],
        },
        "waivers": [],
        "expiresWhen": ["contract changes"],
        "nextDecision": "review",
    }


def _write_gate_outputs(
    root: Path,
    evidence: dict[str, Any],
    *,
    status: str = "old status\n",
) -> tuple[Path, Path]:
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    evidence_path = docs / "G0A_GATE_EVIDENCE_2026-07-17.json"
    status_path = docs / "STATUS.md"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    status_path.write_text(status, encoding="utf-8")
    return evidence_path, status_path


def _full_verification_environment() -> dict[str, Any]:
    return {
        "platform": "Windows-test",
        "pythonExecutable": "python",
        "pythonVersion": "3.13.5",
        "pythonInstalledDistributionsSha256": _fixture_sha256("python-distributions"),
        "pythonLockStatus": "match",
        "pythonLockMismatches": [],
        "rustcVersion": f"rustc {REQUIRED_RUST_VERSION} (test)",
        "cargoVersion": f"cargo {REQUIRED_RUST_VERSION} (test)",
        "requiredRustVersion": REQUIRED_RUST_VERSION,
        "rustVersionMeetsWorkspace": True,
        "nodeVersion": "v24.0.0",
        "lockFileSha256": {
            "Cargo.lock": _fixture_sha256("Cargo.lock"),
            "poetry.lock": _fixture_sha256("poetry.lock"),
        },
    }


def _append_test_run(
    evidence: dict[str, Any],
    *,
    result: str,
    protocols: list[str] | None = None,
) -> None:
    run_suffix = f"test-{len(evidence['source'].get('verificationRuns', []))}"
    gate_evidence._append_verification_run(
        evidence,
        result=result,
        protocols=protocols or list(G0A_REQUIRED_PROTOCOL_ORDER),
        environment=_full_verification_environment(),
        started_at=gate_evidence._utc_timestamp(),
        platform_family="windows",
        remote_provenance=(_remote_provenance(run_suffix) if result == "pass" else None),
    )


def test_generated_outputs_are_excluded_and_refresh_is_idempotent(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    (root / "work.txt").write_text("untracked input\n", encoding="utf-8")
    first, fingerprint = refresh_evidence(root, _evidence())
    write_generated_outputs(
        root,
        Path("docs/G0A_GATE_EVIDENCE_2026-07-17.json"),
        Path("docs/STATUS.md"),
        first,
    )
    second, second_fingerprint = refresh_evidence(root, first)

    assert fingerprint == second_fingerprint
    assert first == second
    assert fingerprint.sha256 == fingerprint_workspace(root).sha256
    assert first["source"]["worktreeFingerprintSchema"] == FINGERPRINT_SCHEMA
    assert RNG_VERIFIED_CLAIM not in first["claims"]["allowed"]
    assert ADR_EXECUTABLE_CLAIM not in first["claims"]["allowed"]
    assert PLATFORM_REVIEW_CLAIM not in first["claims"]["allowed"]
    assert not any(claim.endswith(WORKTREE_VERIFICATION_CLAIM_SUFFIX) for claim in first["claims"]["allowed"])
    assert all(
        item["result"] == "pending" for item in first["evidence"] if item["kind"] == "SoftwareVerificationEvidence"
    )


def test_any_input_content_change_invalidates_fingerprint(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    path = root / "input.txt"
    path.write_text("one\n", encoding="utf-8")
    first = fingerprint_workspace(root)
    path.write_text("two\n", encoding="utf-8")
    second = fingerprint_workspace(root)
    assert first.sha256 != second.sha256


def test_passed_decision_rejects_unresolved_requirements(
    ignore_gate_policy: None,
) -> None:
    evidence = _passing_evidence()
    evidence["requirements"][0]["status"] = "failed"
    with pytest.raises(ValueError, match="GateEvidence"):
        validate_passed_decision(evidence, verify_current_workspace=False)


def _passing_evidence() -> dict[str, Any]:
    evidence = _evidence()
    evidence["decision"] = "passed"
    evidence["source"] = {
        "subjectCommit": "a" * 40,
        "subjectTree": "b" * 40,
        "worktreeDirty": False,
        "worktreeStatusEntryCount": 0,
        "worktreeFingerprintSchema": FINGERPRINT_SCHEMA,
        "worktreeInventorySha256": "0" * 64,
        "excludedGeneratedPaths": [
            "docs/G0A_GATE_EVIDENCE_2026-07-17.json",
            "docs/STATUS.md",
        ],
        "verificationRuns": [
            _verification_run(
                "windows",
                "1",
                started_at="2026-07-17T04:27:00Z",
                finished_at="2026-07-17T04:28:00Z",
            ),
            _verification_run(
                "linux",
                "2",
                started_at="2026-07-17T04:29:00Z",
                finished_at="2026-07-17T04:30:00Z",
            ),
        ],
    }
    for requirement in evidence["requirements"]:
        requirement["status"] = "passed"
        terminal = requirement["terminalEvidence"]
        if terminal is not None:
            terminal["result"] = "accepted_terminal"
            item = next(item for item in evidence["evidence"] if item["evidenceId"] == terminal["evidenceId"])
            item["result"] = "accepted_terminal"
    evidence["blockers"] = []
    evidence["owner"] = _account("owner", role="code-owner")
    evidence["reviewers"] = [
        {
            "provider": "test",
            "stableAccountId": "account:architecture-reviewer",
            "login": "architecture-reviewer",
            "displayName": "Architecture Reviewer",
            "roles": ["architecture"],
            "reviewedSubjectCommit": "a" * 40,
            "reviewedSubjectTree": "b" * 40,
            "reviewUrl": "https://example.invalid/reviews/1",
            "reviewId": "review:1",
            "decision": "accepted",
            "reviewedAt": "2026-07-17T04:29:00Z",
            "conflictOfInterest": False,
        },
        {
            "provider": "test",
            "stableAccountId": "account:migration-reviewer",
            "login": "migration-reviewer",
            "displayName": "Migration Reviewer",
            "roles": ["migration"],
            "reviewedSubjectCommit": "a" * 40,
            "reviewedSubjectTree": "b" * 40,
            "reviewUrl": "https://example.invalid/reviews/2",
            "reviewId": "review:2",
            "decision": "accepted",
            "reviewedAt": "2026-07-17T04:29:30Z",
            "conflictOfInterest": False,
        },
    ]
    evidence["deliveryReadiness"]["workPackages"] = [
        {
            "id": package_id,
            "status": "ready",
            "owner": {
                "provider": "test",
                "stableAccountId": f"account:owner:{package_id}",
                "login": f"owner-{package_id}",
                "displayName": f"Owner {package_id}",
                "role": "work-package-owner",
            },
            "reviewers": [
                {
                    "provider": "test",
                    "stableAccountId": f"account:reviewer:{package_id}",
                    "login": f"reviewer-{package_id}",
                    "displayName": f"Reviewer {package_id}",
                    "roles": ["architecture"],
                    "reviewedSubjectCommit": "a" * 40,
                    "reviewedSubjectTree": "b" * 40,
                    "reviewUrl": f"https://example.invalid/reviews/{package_id}",
                    "reviewId": f"review:{package_id}",
                    "decision": "accepted",
                    "reviewedAt": "2026-07-17T04:29:00Z",
                    "conflictOfInterest": False,
                }
            ],
            "capacity": {
                "availablePersonHours": 40,
                "periodStart": "2026-07-17",
                "periodEnd": "2099-07-24",
            },
            "estimate": {
                "method": "three-point",
                "unit": "person-hours",
                "optimistic": 4,
                "mostLikely": 8,
                "pessimistic": 16,
            },
            "wip": {
                "globalLimit": 2,
                "slot": ("WIP-GATE" if package_id.startswith("R0A") else "QUEUED-DOMAIN"),
            },
            "timebox": {
                "startsAt": "2026-07-17T00:00:00Z",
                "endsAt": "2099-07-24T00:00:00Z",
            },
            "scopeReductionRule": "stop at the smallest complete contract slice",
            "approvalReference": f"https://example.invalid/readiness/{package_id}",
            "expiresAt": "2099-07-24T00:00:00Z",
        }
        for package_id in sorted(G0A_REQUIRED_DELIVERY_WORK_PACKAGE_IDS)
    ]
    evidence["claims"]["forbidden"] = []
    evidence["claims"]["allowed"].append("G0A has passed")
    return evidence


def test_passed_decision_requires_every_independent_condition(
    ignore_gate_policy: None,
) -> None:
    validate_passed_decision(
        _passing_evidence(),
        verify_current_workspace=False,
    )

    invalid_cases: list[dict[str, Any]] = []
    dirty = _passing_evidence()
    dirty["source"]["worktreeDirty"] = True
    invalid_cases.append(dirty)

    stale = _passing_evidence()
    stale["evidence"][0]["result"] = "pending"
    invalid_cases.append(stale)

    invalid_coverage = _passing_evidence()
    invalid_coverage["evidence"][0]["verificationMode"] = "covered_by_parent"
    invalid_coverage["evidence"][0]["coveredBy"] = "missing parent"
    invalid_coverage["evidence"][0].pop("executedCommand")
    invalid_cases.append(invalid_coverage)

    blocked = _passing_evidence()
    blocked["blockers"] = [{"id": "B", "summary": "blocked"}]
    invalid_cases.append(blocked)

    no_owner = _passing_evidence()
    no_owner["owner"] = "unassigned"
    invalid_cases.append(no_owner)

    no_reviewer = _passing_evidence()
    no_reviewer["reviewers"] = []
    invalid_cases.append(no_reviewer)

    self_review = _passing_evidence()
    self_review["reviewers"] = ["Owner"]
    invalid_cases.append(self_review)

    wrong_review_subject = _passing_evidence()
    wrong_review_subject["reviewers"][0]["reviewedSubjectCommit"] = "c" * 40
    invalid_cases.append(wrong_review_subject)

    owner_as_reviewer = _passing_evidence()
    owner_as_reviewer["reviewers"][0]["stableAccountId"] = "account:owner"
    invalid_cases.append(owner_as_reviewer)

    missing_environment = _passing_evidence()
    missing_environment["source"].pop("verificationRuns")
    invalid_cases.append(missing_environment)

    missing_waiver = _passing_evidence()
    missing_waiver["requirements"][0]["status"] = "waived"
    invalid_cases.append(missing_waiver)

    expired_waiver = _passing_evidence()
    expired_waiver["requirements"][0]["status"] = "waived"
    expired_waiver["waivers"] = [
        _waiver(
            expired_waiver["requirements"][0]["id"],
            expires_at="2026-07-17T00:00:00Z",
        )
    ]
    invalid_cases.append(expired_waiver)

    orphan_waiver = _passing_evidence()
    orphan_waiver["waivers"] = [_waiver("R0A-05", expires_at="2026-07-18T00:00:00Z")]
    invalid_cases.append(orphan_waiver)

    for invalid in invalid_cases:
        with pytest.raises(ValueError, match="GateEvidence"):
            validate_passed_decision(
                invalid,
                verify_current_workspace=False,
            )


def test_g0a_contract_uses_the_literal_ten_requirement_set() -> None:
    expected = {
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
    policy = json.loads((gate_evidence.ROOT / gate_evidence.GATE_POLICY_PATH).read_text(encoding="utf-8"))

    assert G0A_REQUIRED_REQUIREMENT_IDS == expected
    assert set(policy["requirements"]) == expected
    assert len(policy["requirements"]) == 10


def test_delivery_readiness_is_required_for_every_r0a_and_r1_package(
    ignore_gate_policy: None,
) -> None:
    evidence = _passing_evidence()
    evidence["deliveryReadiness"]["workPackages"].pop()

    with pytest.raises(ValueError, match="GateEvidence|[Dd]eliveryReadiness"):
        validate_passed_decision(
            evidence,
            verify_current_workspace=False,
            now=datetime(2026, 7, 19, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capacity", {"availablePersonHours": 0, "periodStart": "2026-07-17", "periodEnd": "2026-07-24"}),
        (
            "estimate",
            {
                "method": "three-point",
                "unit": "person-hours",
                "optimistic": 8,
                "mostLikely": 4,
                "pessimistic": 2,
            },
        ),
        ("wip", {"globalLimit": 0, "slot": "WIP-GATE"}),
        (
            "timebox",
            {
                "startsAt": "2026-07-18T00:00:00Z",
                "endsAt": "2026-07-18T01:00:00Z",
            },
        ),
        ("approvalReference", "not-a-uri"),
        ("expiresAt", "2026-07-18T00:00:00Z"),
    ],
)
def test_delivery_readiness_rejects_untrusted_fields(
    ignore_gate_policy: None,
    field: str,
    value: Any,
) -> None:
    evidence = _passing_evidence()
    evidence["deliveryReadiness"]["workPackages"][0][field] = value

    with pytest.raises(ValueError, match="GateEvidence|[Dd]eliveryReadiness"):
        validate_passed_decision(
            evidence,
            verify_current_workspace=False,
            now=datetime(2026, 7, 19, tzinfo=timezone.utc),
        )


def test_delivery_readiness_rejects_owner_self_review(
    ignore_gate_policy: None,
) -> None:
    evidence = _passing_evidence()
    record = evidence["deliveryReadiness"]["workPackages"][0]
    record["reviewers"][0]["stableAccountId"] = record["owner"]["stableAccountId"]

    with pytest.raises(ValueError, match="self-review"):
        validate_passed_decision(
            evidence,
            verify_current_workspace=False,
            now=datetime(2026, 7, 19, tzinfo=timezone.utc),
        )


def test_passed_decision_requires_latest_verification_run_to_pass(
    ignore_gate_policy: None,
) -> None:
    evidence = _passing_evidence()
    _append_test_run(
        evidence,
        result="fail",
        protocols=[gate_evidence.FINAL_DOCS_CHECK_PROTOCOL],
    )
    with pytest.raises(ValueError, match="latest verification run"):
        validate_passed_decision(evidence, verify_current_workspace=False)
    assert "last_verified: not-verified" in gate_evidence.render_status(evidence)


def test_historical_protocol_does_not_poison_the_latest_passing_run(
    ignore_gate_policy: None,
) -> None:
    evidence = _passing_evidence()
    historical = json.loads(json.dumps(evidence["source"]["verificationRuns"][0]))
    historical["runId"] = "gate-run:" + ("2" * 32)
    historical["startedAt"] = "2026-07-16T04:29:00Z"
    historical["finishedAt"] = "2026-07-16T04:30:00Z"
    historical["protocols"] = ["legacy pytest protocol"]
    evidence["source"]["verificationRuns"].insert(0, historical)

    validate_passed_decision(evidence, verify_current_workspace=False)


def test_worktree_claim_tracks_clean_or_dirty_source() -> None:
    evidence = _evidence()
    _set_verified_worktree_claims(evidence, verified=True, dirty=False)
    assert f"the recorded clean {WORKTREE_VERIFICATION_CLAIM_SUFFIX}" in evidence["claims"]["allowed"]
    assert not any("dirty worktree passes" in claim for claim in evidence["claims"]["allowed"])


def test_mid_gate_failure_leaves_all_unexecuted_evidence_stale(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence = _evidence()
    evidence["source"] = {
        "subjectCommit": "a" * 40,
        "subjectTree": "b" * 40,
        "worktreeDirty": True,
        "verificationRuns": [],
    }
    protocols = ("gate-one", "covered-test", "gate-two", "gate-three")
    evidence["evidence"] = [
        {
            "kind": "SoftwareVerificationEvidence",
            "path": "test",
            "protocol": protocol,
            "result": "pass",
        }
        for protocol in protocols
    ]
    commands = (
        ("gate-one", lambda root: ["gate-one"], "one passed"),
        ("gate-two", lambda root: ["gate-two"], "two passed"),
        ("gate-three", lambda root: ["gate-three"], "three passed"),
    )
    return_codes = iter((0, 9))

    monkeypatch.setattr(gate_evidence, "VERIFICATION_COMMANDS", commands)
    monkeypatch.setattr(
        gate_evidence,
        "_validate_repository_python",
        lambda root: tmp_path / "python",
    )
    monkeypatch.setattr(
        gate_evidence,
        "_verification_environment",
        lambda root: _full_verification_environment(),
    )
    monkeypatch.setattr(
        gate_evidence.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=next(return_codes)),
    )

    assert verify_commands(tmp_path, evidence) is False
    results = {item["protocol"]: item["result"] for item in evidence["evidence"]}
    assert results == {
        "gate-one": "pass",
        "covered-test": "pending",
        "gate-two": "fail",
        "gate-three": "pending",
    }
    assert evidence["source"]["verificationRuns"][0]["result"] == "fail"
    assert evidence["source"]["verificationRuns"][0]["environment"]["toolchain"]["python"] == "3.13.5"


def test_verification_rejects_non_repository_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _evidence()
    evidence["source"] = {
        "subjectCommit": "a" * 40,
        "subjectTree": "b" * 40,
        "worktreeDirty": True,
        "verificationRuns": [],
    }

    def reject_interpreter(root: Path) -> Path:
        raise RuntimeError("wrong interpreter")

    monkeypatch.setattr(
        gate_evidence,
        "_validate_repository_python",
        reject_interpreter,
    )

    assert verify_commands(Path("."), evidence) is False
    software = [item for item in evidence["evidence"] if item["kind"] == "SoftwareVerificationEvidence"]
    assert software[0]["result"] == "fail"
    assert software[0]["verificationMode"] == "not_run"
    assert all(item["result"] == "pending" for item in software[1:])
    assert len(evidence["source"]["verificationRuns"]) == 1
    run = evidence["source"]["verificationRuns"][0]
    assert run["result"] == "fail"
    assert run["protocols"] == [gate_evidence.PYTHON_GATE_PROTOCOL]


def test_repository_python_preserves_virtual_environment_launcher(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, "-I", "-m", "venv", "--without-pip", str(tmp_path / ".venv")],
        check=True, capture_output=True,
    )
    executable = gate_evidence.repository_python(tmp_path)
    completed = subprocess.run(
        [str(executable), "-I", "-c", "import sys; print(sys.prefix)"],
        check=True, capture_output=True, text=True,
    )
    assert Path(completed.stdout.strip()).resolve() == (tmp_path / ".venv").resolve()


def test_base_python_cannot_impersonate_symlinked_repository_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    subprocess.run(
        [sys.executable, "-I", "-m", "venv", "--without-pip", str(tmp_path / ".venv")],
        check=True, capture_output=True,
    )
    executable = gate_evidence.repository_python(tmp_path)
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "prefix", sys.base_prefix)
    with pytest.raises(RuntimeError, match="repository interpreter"):
        gate_evidence._validate_repository_python(tmp_path)


def test_targeted_python_verification_uses_native_path_separators(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(gate_evidence, "repository_python", lambda root: tmp_path / "python")
    factory = next(
        factory for protocol, factory, _ in gate_evidence.VERIFICATION_COMMANDS
        if protocol == gate_evidence.TARGETED_PYTHON_PROTOCOL
    )
    assert factory(tmp_path)[-2] == str(Path("tests") / "core" / "test_adr_011_contract.py")


def test_verify_persists_blocked_checkpoint_before_preflight(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    evidence = _passing_evidence()
    evidence_path, status_path = _write_gate_outputs(
        root,
        evidence,
        status="old passed status\n",
    )
    observed_decisions: list[str] = []

    def fail_preflight(root_arg: Path, candidate: dict[str, Any]) -> bool:
        on_disk = json.loads(evidence_path.read_text(encoding="utf-8"))
        observed_decisions.append(on_disk["decision"])
        assert on_disk["decision"] == "blocked"
        assert "not-verified" in status_path.read_text(encoding="utf-8")
        _append_test_run(
            candidate,
            result="fail",
            protocols=[gate_evidence.PYTHON_GATE_PROTOCOL],
        )
        return False

    monkeypatch.setattr(gate_evidence, "verify_commands", fail_preflight)

    result = gate_evidence.generate(
        root,
        evidence_path.relative_to(root),
        status_path.relative_to(root),
        verify=True,
    )

    persisted = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result == 1
    assert observed_decisions == ["blocked"]
    assert persisted["decision"] == "blocked"
    assert persisted["source"]["verificationRuns"][-1]["result"] == "fail"
    assert "G0A has passed" in persisted["claims"]["forbidden"]


def test_generate_preserves_the_specific_command_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    evidence_path, status_path = _write_gate_outputs(root, _evidence())

    def fail_command(root_arg: Path, candidate: dict[str, Any]) -> bool:
        item = next(
            item for item in candidate["evidence"] if item.get("protocol") == gate_evidence.PYTHON_GATE_PROTOCOL
        )
        item.update(
            {
                "result": "fail",
                "details": "sentinel command failure",
                "verificationMode": "direct",
                "executedCommand": "sentinel",
            }
        )
        _append_test_run(
            candidate,
            result="fail",
            protocols=[gate_evidence.PYTHON_GATE_PROTOCOL],
        )
        return False

    monkeypatch.setattr(gate_evidence, "verify_commands", fail_command)

    assert (
        gate_evidence.generate(
            root,
            evidence_path.relative_to(root),
            status_path.relative_to(root),
            verify=True,
        )
        == 1
    )

    persisted = json.loads(evidence_path.read_text(encoding="utf-8"))
    item = next(item for item in persisted["evidence"] if item.get("protocol") == gate_evidence.PYTHON_GATE_PROTOCOL)
    assert item["result"] == "fail"
    assert item["details"] == "sentinel command failure"
    assert item["executedCommand"] == "sentinel"


def test_command_launch_exception_is_recorded_as_failed_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence = _evidence()
    evidence["source"] = {
        "subjectCommit": "a" * 40,
        "subjectTree": "b" * 40,
        "worktreeDirty": True,
        "verificationRuns": [],
    }
    monkeypatch.setattr(
        gate_evidence,
        "VERIFICATION_COMMANDS",
        (
            (
                gate_evidence.PYTHON_GATE_PROTOCOL,
                lambda root: ["gate-one"],
                "passed",
            ),
        ),
    )
    monkeypatch.setattr(
        gate_evidence,
        "_validate_repository_python",
        lambda root: tmp_path / "python",
    )
    monkeypatch.setattr(
        gate_evidence,
        "_verification_environment",
        lambda root: _full_verification_environment(),
    )

    def raise_os_error(*args: Any, **kwargs: Any) -> Any:
        raise OSError("cannot launch")

    monkeypatch.setattr(gate_evidence.subprocess, "run", raise_os_error)

    assert verify_commands(tmp_path, evidence) is False
    run = evidence["source"]["verificationRuns"][-1]
    assert run["result"] == "fail"
    assert run["protocols"] == [gate_evidence.PYTHON_GATE_PROTOCOL]
    item = next(item for item in evidence["evidence"] if item.get("protocol") == gate_evidence.PYTHON_GATE_PROTOCOL)
    assert item["result"] == "fail"
    assert item["verificationMode"] == "not_run"
    assert "OSError" in item["details"]


def test_blocked_status_never_presents_historical_pass_as_current() -> None:
    evidence = _passing_evidence()
    evidence["decision"] = "blocked"
    rendered = gate_evidence.render_status(evidence)
    assert "last_verified: not-verified" in rendered
    assert "| G0A | `blocked` | clean (0 entries) | not-verified |" in rendered
    assert "2026-07-17T04:30:00Z" not in rendered


def test_output_tear_keeps_blocked_authority_and_rolls_back_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path
    evidence_path = Path("docs/G0A_GATE_EVIDENCE_2026-07-17.json")
    status_path = Path("docs/STATUS.md")
    blocked = _passing_evidence()
    blocked["decision"] = "blocked"
    _write_gate_outputs(root, blocked, status="old passed status\n")
    real_replace = gate_evidence._replace_prepared_text

    def fail_status_replace(temporary: Path, target: Path) -> None:
        if target.name == "STATUS.md":
            raise OSError("status replace failed")
        real_replace(temporary, target)

    monkeypatch.setattr(
        gate_evidence,
        "_replace_prepared_text",
        fail_status_replace,
    )
    with pytest.raises(OSError, match="status replace failed"):
        write_generated_outputs(root, evidence_path, status_path, blocked)

    persisted = json.loads((root / evidence_path).read_text(encoding="utf-8"))
    assert persisted["decision"] == "blocked"
    assert not (root / status_path).exists()

    monkeypatch.setattr(
        gate_evidence,
        "_replace_prepared_text",
        real_replace,
    )
    write_generated_outputs(root, evidence_path, status_path, blocked)
    assert (root / status_path).read_text(encoding="utf-8") == (gate_evidence.render_status(blocked))

    passing = json.loads(json.dumps(blocked))
    passing["decision"] = "passed"
    remaining_status_failures = 1

    def fail_status_once(temporary: Path, target: Path) -> None:
        nonlocal remaining_status_failures
        if target.name == "STATUS.md" and remaining_status_failures:
            remaining_status_failures -= 1
            raise OSError("status replace failed")
        real_replace(temporary, target)

    monkeypatch.setattr(
        gate_evidence,
        "_replace_prepared_text",
        fail_status_once,
    )
    with pytest.raises(OSError, match="status replace failed"):
        write_generated_outputs(root, evidence_path, status_path, passing)

    rolled_back = json.loads((root / evidence_path).read_text(encoding="utf-8"))
    assert rolled_back["decision"] == "blocked"
    assert (root / status_path).read_text(encoding="utf-8") == (gate_evidence.render_status(blocked))
    assert not list((root / "docs").glob("*.tmp"))


def test_verified_at_requires_iso_and_verify_mode() -> None:
    assert _validated_verified_at("2026-07-17T04:30:00Z") == "2026-07-17T04:30:00Z"
    with pytest.raises(ValueError, match="ending in Z"):
        _validated_verified_at("2026-07-17")
    with pytest.raises(ValueError, match="ending in Z"):
        _validated_verified_at("2026-07-17T12:30:00+08:00")
    with pytest.raises(ValueError, match="UTC"):
        _validated_verified_at("17/07/2026")


def test_manifest_rejects_missing_required_items_and_future_verification() -> None:
    missing_requirement = _passing_evidence()
    missing_requirement["requirements"].pop()
    with pytest.raises(ValueError, match="requirement IDs differ"):
        validate_gate_evidence_manifest(missing_requirement)

    missing_protocol = _passing_evidence()
    missing_protocol["evidence"] = [
        item for item in missing_protocol["evidence"] if item.get("protocol") != TARGETED_RNG_RUST_PROTOCOL
    ]
    with pytest.raises(ValueError, match="protocols differ"):
        validate_gate_evidence_manifest(missing_protocol)

    future = _passing_evidence()
    future_run = future["source"]["verificationRuns"][0]
    future_run["startedAt"] = "2026-07-18T00:00:00Z"
    future_run["finishedAt"] = "2026-07-18T00:01:00Z"
    with pytest.raises(ValueError, match="future"):
        validate_gate_evidence_manifest(
            future,
            now=datetime(2026, 7, 17, tzinfo=timezone.utc),
        )


def test_historical_run_does_not_require_the_current_runtime_to_match(
    monkeypatch: pytest.MonkeyPatch,
    ignore_gate_policy: None,
) -> None:
    evidence = _passing_evidence()
    monkeypatch.setattr(
        gate_evidence,
        "_verification_environment",
        lambda root: {"platform": "different-runtime"},
    )
    validate_passed_decision(evidence, verify_current_workspace=False)


def test_attestation_commit_can_follow_the_subject_without_self_reference(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    subject = fingerprint_workspace(root)
    subject_tree = subprocess.run(
        ["git", "rev-parse", f"{subject.base_commit}^{{tree}}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source = {
        "subjectCommit": subject.base_commit,
        "subjectTree": subject_tree,
        "worktreeDirty": subject.dirty,
        "worktreeStatusEntryCount": subject.status_entry_count,
        "worktreeFingerprintSchema": FINGERPRINT_SCHEMA,
        "worktreeInventorySha256": subject.sha256,
    }
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs/G0A_GATE_EVIDENCE_2026-07-17.json").write_text("{}\n", encoding="utf-8")
    (root / "docs/STATUS.md").write_text("status\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "attest subject")

    assert _subject_attestation_issues({"source": source}, root=root) == []

    (root / "README.md").write_text("changed after attestation\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "change source")
    assert any("non-generated paths" in issue for issue in _subject_attestation_issues({"source": source}, root=root))


def test_passed_content_hashes_are_recomputed_from_subject(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    for name, content in (("Cargo.lock", "cargo\n"), ("poetry.lock", "poetry\n")):
        (root / name).write_text(content, encoding="utf-8")
    _git(root, "add", "Cargo.lock", "poetry.lock")
    _git(root, "commit", "-m", "add locks")

    subject = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subject_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    evidence = _passing_evidence()
    evidence["source"]["subjectCommit"] = subject
    evidence["source"]["subjectTree"] = subject_tree

    readme_hash = hashlib.sha256(b"baseline\n").hexdigest()
    for item in evidence["evidence"]:
        if "sha256" in item:
            item["sha256"] = readme_hash
    for requirement in evidence["requirements"]:
        if requirement["terminalEvidence"] is not None:
            requirement["terminalEvidence"]["sha256"] = readme_hash
    lock_hashes = {
        name: hashlib.sha256(
            subprocess.run(
                ["git", "show", f"{subject}:{name}"],
                cwd=root,
                check=True,
                capture_output=True,
            ).stdout
        ).hexdigest()
        for name in ("Cargo.lock", "poetry.lock")
    }
    for run in evidence["source"]["verificationRuns"]:
        run["environment"]["lockFileSha256"] = dict(lock_hashes)

    assert _subject_content_issues(evidence, root=root) == []

    evidence["evidence"][-1]["sha256"] = "0" * 64
    assert any("hashed evidence differs" in issue for issue in _subject_content_issues(evidence, root=root))
    evidence["evidence"][-1]["sha256"] = readme_hash

    evidence["source"]["verificationRuns"][0]["environment"]["lockFileSha256"]["Cargo.lock"] = "0" * 64
    assert any("lock-file hashes differ" in issue for issue in _subject_content_issues(evidence, root=root))


def test_v1_migration_never_inherits_a_passed_decision(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    legacy = _evidence()
    legacy["$schema"] = "GATE_EVIDENCE_MANIFEST_V1.schema.json"
    legacy["schemaVersion"] = "telysta-gate-evidence-manifest.v1"
    legacy["decision"] = "passed"
    legacy["source"] = {
        "baseCommit": "a" * 40,
        "worktreeDirty": False,
        "worktreeStatusEntryCount": 0,
        "worktreeFingerprintSchema": "telysta-git-worktree-fingerprint.v1",
        "worktreeInventorySha256": "0" * 64,
        "excludedGeneratedPaths": [
            "docs/G0A_GATE_EVIDENCE_2026-07-17.json",
            "docs/STATUS.md",
        ],
        "environment": "legacy",
    }
    migrated, _ = refresh_evidence(root, legacy)
    assert migrated["schemaVersion"] == gate_evidence.GATE_EVIDENCE_SCHEMA_VERSION
    assert migrated["decision"] == "blocked"
    assert "G0A has passed" in migrated["claims"]["forbidden"]
    assert all(
        item["result"] == "pending" for item in migrated["evidence"] if item["kind"] == "SoftwareVerificationEvidence"
    )


def test_v2_migration_clears_pass_reviews_and_adds_new_requirements(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    legacy = _passing_evidence()
    legacy["$schema"] = "GATE_EVIDENCE_MANIFEST_V2.schema.json"
    legacy["schemaVersion"] = "telysta-gate-evidence-manifest.v2"
    legacy.pop("gatePolicy")
    legacy.pop("deliveryReadiness")
    legacy["requirements"] = [
        requirement
        for requirement in legacy["requirements"]
        if requirement["id"]
        not in {
            "R0A-08",
            "R0A-09",
            "R0A-10",
        }
    ]

    migrated, _ = refresh_evidence(root, legacy)

    assert migrated["schemaVersion"] == gate_evidence.GATE_EVIDENCE_SCHEMA_VERSION
    assert migrated["decision"] == "blocked"
    assert migrated["reviewers"] == []
    assert migrated["waivers"] == []
    assert migrated["deliveryReadiness"]["workPackages"] == []
    assert {requirement["id"] for requirement in migrated["requirements"]} == G0A_REQUIRED_REQUIREMENT_IDS
    assert any(blocker["id"] == "G0A-B97" for blocker in migrated["blockers"])


def test_refresh_after_subject_lock_change_persists_blocked_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    for relative in (
        gate_evidence.GATE_EVIDENCE_SCHEMA_PATH,
        gate_evidence.GATE_EVIDENCE_V1_SCHEMA_PATH,
    ):
        target = root / relative
        target.write_bytes((gate_evidence.ROOT / relative).read_bytes())
    (root / "Cargo.lock").write_text("cargo-one\n", encoding="utf-8")
    (root / "poetry.lock").write_text("poetry-one\n", encoding="utf-8")
    _git(root, "add", "Cargo.lock", "poetry.lock", "docs")
    _git(root, "commit", "-m", "add gate inputs")

    subject = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subject_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    fingerprint = fingerprint_workspace(root)
    evidence = _passing_evidence()
    source = evidence["source"]
    source["subjectCommit"] = subject
    source["subjectTree"] = subject_tree
    source["worktreeDirty"] = fingerprint.dirty
    source["worktreeStatusEntryCount"] = fingerprint.status_entry_count
    source["worktreeInventorySha256"] = fingerprint.sha256
    lock_hashes = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ("Cargo.lock", "poetry.lock")
    }
    for run in source["verificationRuns"]:
        run["subjectCommit"] = subject
        run["subjectTree"] = subject_tree
        run["environment"]["lockFileSha256"] = dict(lock_hashes)
    for reviewer in evidence["reviewers"]:
        reviewer["reviewedSubjectCommit"] = subject
        reviewer["reviewedSubjectTree"] = subject_tree
    for package in evidence["deliveryReadiness"]["workPackages"]:
        for reviewer in package["reviewers"]:
            reviewer["reviewedSubjectCommit"] = subject
            reviewer["reviewedSubjectTree"] = subject_tree
    readme_hash = hashlib.sha256(b"baseline\n").hexdigest()
    for item in evidence["evidence"]:
        if "sha256" in item:
            item["sha256"] = readme_hash
    for requirement in evidence["requirements"]:
        if requirement["terminalEvidence"] is not None:
            requirement["terminalEvidence"]["sha256"] = readme_hash
    evidence_path, status_path = _write_gate_outputs(
        root,
        evidence,
        status=gate_evidence.render_status(evidence),
    )

    (root / "Cargo.lock").write_text("cargo-two\n", encoding="utf-8")
    _git(root, "add", "Cargo.lock")
    _git(root, "commit", "-m", "change lock after attestation")
    monkeypatch.setattr(
        gate_evidence,
        "_gate_policy_issues",
        lambda evidence, root: [],
    )

    result = gate_evidence.generate(
        root,
        evidence_path.relative_to(root),
        status_path.relative_to(root),
        verify=False,
    )

    persisted = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result == 1
    assert persisted["decision"] == "blocked"
    # This fixture deliberately lacks Cargo.toml, so v3 cannot honestly encode
    # a complete current environment for a new formal failure run. The old run
    # remains historical while the decision and software claims fail closed.
    assert len(persisted["source"]["verificationRuns"]) == 2
    assert all(
        item["result"] == "pending"
        for item in persisted["evidence"]
        if item["kind"] == "SoftwareVerificationEvidence" and "protocol" in item
    )
    assert any(blocker["id"] == gate_evidence.VERIFICATION_FAILURE_BLOCKER_ID for blocker in persisted["blockers"])
    assert "last_verified: not-verified" in status_path.read_text(encoding="utf-8")


def test_workspace_change_during_verification_marks_run_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    evidence_path, status_path = _write_gate_outputs(root, _evidence())

    def passing_commands(root_arg: Path, candidate: dict[str, Any]) -> bool:
        _append_test_run(candidate, result="pass")
        gate_evidence._set_verified_worktree_claims(
            candidate,
            verified=True,
            dirty=candidate["source"]["worktreeDirty"],
        )
        (root_arg / "changed-during-gate.txt").write_text(
            "changed\n",
            encoding="utf-8",
        )
        return True

    real_run = subprocess.run

    def run_with_passing_docs(command: list[str], *args: Any, **kwargs: Any) -> Any:
        if "scripts/docs_check.py" in command:
            return SimpleNamespace(returncode=0)
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(gate_evidence, "verify_commands", passing_commands)
    monkeypatch.setattr(gate_evidence.subprocess, "run", run_with_passing_docs)

    result = gate_evidence.generate(
        root,
        evidence_path.relative_to(root),
        status_path.relative_to(root),
        verify=True,
    )

    persisted = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result == 1
    assert persisted["decision"] == "blocked"
    assert persisted["source"]["verificationRuns"][-1]["result"] == "fail"
    assert any(
        "changed during verification" in blocker["summary"]
        for blocker in persisted["blockers"]
        if blocker["id"] == gate_evidence.VERIFICATION_FAILURE_BLOCKER_ID
    )


def test_final_docs_failure_appends_failure_run_and_stays_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    evidence_path, status_path = _write_gate_outputs(root, _evidence())

    def passing_commands(root_arg: Path, candidate: dict[str, Any]) -> bool:
        _append_test_run(candidate, result="pass")
        return True

    real_run = subprocess.run

    def run_with_failing_docs(command: list[str], *args: Any, **kwargs: Any) -> Any:
        if "scripts/docs_check.py" in command:
            return SimpleNamespace(returncode=7)
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(gate_evidence, "verify_commands", passing_commands)
    monkeypatch.setattr(gate_evidence.subprocess, "run", run_with_failing_docs)

    result = gate_evidence.generate(
        root,
        evidence_path.relative_to(root),
        status_path.relative_to(root),
        verify=True,
    )

    persisted = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result == 7
    assert persisted["decision"] == "blocked"
    assert persisted["source"]["verificationRuns"][-1]["result"] == "fail"
    assert persisted["source"]["verificationRuns"][-1]["protocols"] == [gate_evidence.FINAL_DOCS_CHECK_PROTOCOL]


def test_failure_run_ids_do_not_collide_within_one_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _passing_evidence()
    evidence["source"]["verificationRuns"] = []
    monkeypatch.setattr(
        gate_evidence,
        "_utc_timestamp",
        lambda: "2026-07-19T00:00:00Z",
    )

    _append_test_run(evidence, result="fail")
    _append_test_run(evidence, result="fail")

    run_ids = [run["runId"] for run in evidence["source"]["verificationRuns"]]
    assert len(run_ids) == len(set(run_ids)) == 2


def test_gate_policy_rejects_proposed_architecture_decisions() -> None:
    evidence = json.loads((gate_evidence.ROOT / gate_evidence.DEFAULT_EVIDENCE_PATH).read_text(encoding="utf-8"))
    issues = _gate_policy_issues(evidence, root=gate_evidence.ROOT)
    assert any("ADR-011" in issue and "got proposed" in issue for issue in issues)
    assert any("ADR-012" in issue and "got proposed" in issue for issue in issues)
    assert any("ADR-013" in issue and "got proposed" in issue for issue in issues)


def test_gate_policy_requires_all_terminal_evidence() -> None:
    evidence = json.loads((gate_evidence.ROOT / gate_evidence.DEFAULT_EVIDENCE_PATH).read_text(encoding="utf-8"))
    issues = _gate_policy_issues(evidence, root=gate_evidence.ROOT)

    for requirement_id in ("R0A-05", "R0A-07", "R0A-08", "R0A-09", "R0A-10"):
        assert any(requirement_id in issue and "terminal" in issue for issue in issues), requirement_id


def test_remote_terminal_evidence_requires_matching_provenance() -> None:
    evidence = _passing_evidence()
    requirement = next(item for item in evidence["requirements"] if item["id"] == "R0A-08")
    terminal = requirement["terminalEvidence"]
    policy = json.loads((gate_evidence.ROOT / gate_evidence.GATE_POLICY_PATH).read_text(encoding="utf-8"))
    terminal_rule = policy["requirements"]["R0A-08"]["terminalAcceptance"]
    terminal["path"] = terminal_rule["evidencePath"]
    terminal["kind"] = terminal_rule["kind"]
    item = next(item for item in evidence["evidence"] if item["evidenceId"] == terminal["evidenceId"])
    item["path"] = terminal["path"]
    item["kind"] = terminal["kind"]

    issues = _gate_policy_issues(evidence, root=gate_evidence.ROOT)

    assert any("R0A-08 terminal evidence lacks remote provenance" in issue for issue in issues)


def test_terminal_software_evidence_is_not_treated_as_a_command_protocol() -> None:
    evidence = _passing_evidence()
    terminal = next(item for item in evidence["evidence"] if item["evidenceId"] == "terminal:r0a-08")

    gate_evidence._synchronize_required_software_items(evidence)
    gate_evidence._mark_software_stale(evidence)

    assert terminal in evidence["evidence"]
    assert terminal["result"] == "accepted_terminal"
    assert "protocol" not in terminal


def test_pass_requires_trusted_windows_and_linux_runs(
    ignore_gate_policy: None,
) -> None:
    evidence = _passing_evidence()
    evidence["source"]["verificationRuns"][1]["remoteProvenance"] = None

    with pytest.raises(ValueError, match="GateEvidence"):
        validate_passed_decision(evidence, verify_current_workspace=False)


def test_manifest_rejects_legacy_policy_even_if_its_hash_is_recorded(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    legacy_payload = (gate_evidence.ROOT / "docs/G0A_POLICY_V1.json").read_bytes()
    (root / gate_evidence.GATE_POLICY_PATH).write_bytes(legacy_payload)
    evidence = _evidence()
    evidence["gatePolicy"]["sha256"] = hashlib.sha256(legacy_payload).hexdigest()

    with pytest.raises(ValueError, match="policy"):
        validate_gate_evidence_manifest(evidence, root=root)


def test_manifest_rejects_policy_hash_drift() -> None:
    evidence = _evidence()
    evidence["gatePolicy"]["sha256"] = "f" * 64

    with pytest.raises(ValueError, match="gatePolicy sha256"):
        validate_gate_evidence_manifest(evidence)


def test_verifier_lease_rejects_concurrent_publication_without_mutation(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    evidence_path, status_path = _write_gate_outputs(root, _evidence())
    original_evidence = evidence_path.read_bytes()
    original_status = status_path.read_bytes()
    lease_path = root / gate_evidence.VERIFIER_LEASE_PATH
    lease_path.write_text("held by test\n", encoding="utf-8")

    result = gate_evidence.generate(
        root,
        evidence_path.relative_to(root),
        status_path.relative_to(root),
    )

    assert result == 1
    assert evidence_path.read_bytes() == original_evidence
    assert status_path.read_bytes() == original_status


def test_verifier_lease_resolves_linked_worktree_git_file_and_keeps_outputs_unchanged(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    root = _repository(repository)
    linked = tmp_path / "linked"
    _git(root, "worktree", "add", "--detach", str(linked), "HEAD")
    assert (linked / ".git").is_file()
    evidence_path, status_path = _write_gate_outputs(linked, _evidence())
    before = evidence_path.read_bytes(), status_path.read_bytes()
    git_path = subprocess.check_output(
        ["git", "rev-parse", "--git-path", gate_evidence.VERIFIER_LEASE_PATH.name], cwd=linked, text=True,
    ).strip()
    lock = Path(git_path)
    if not lock.is_absolute():
        lock = linked / lock
    with gate_evidence.verifier_lease(linked):
        assert lock.is_file()
        assert gate_evidence.generate(linked) == 1
        assert before == (evidence_path.read_bytes(), status_path.read_bytes())
    assert not lock.exists()
    assert (linked / ".git").is_file()


def test_malformed_evidence_is_preserved_and_stale_status_is_removed(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    evidence_path, status_path = _write_gate_outputs(root, _evidence())
    evidence_path.write_text("{not json", encoding="utf-8")
    status_path.write_text("old passed status\n", encoding="utf-8")

    result = gate_evidence.generate(
        root,
        evidence_path.relative_to(root),
        status_path.relative_to(root),
    )

    assert result == 1
    assert evidence_path.read_text(encoding="utf-8") == "{not json"
    assert not status_path.exists()


def test_waiver_is_checked_against_current_time(
    ignore_gate_policy: None,
) -> None:
    evidence = _passing_evidence()
    requirement_id = evidence["requirements"][0]["id"]
    evidence["requirements"][0]["status"] = "waived"
    evidence["waivers"] = [_waiver(requirement_id, expires_at="2026-07-18T00:00:00Z")]
    with pytest.raises(ValueError, match="GateEvidence"):
        validate_passed_decision(
            evidence,
            verify_current_workspace=False,
            now=datetime(2026, 7, 19, tzinfo=timezone.utc),
        )


def test_required_check_does_not_share_a_fixed_pytest_basetemp() -> None:
    check_source = (gate_evidence.ROOT / "scripts/check.py").read_text(encoding="utf-8")
    assert "--basetemp" not in check_source
    assert ".venv/pytest-tmp" not in check_source


def test_targeted_python_gate_uses_the_hermetic_runner() -> None:
    full_gate_factory = next(
        command_factory
        for protocol, command_factory, _ in gate_evidence.VERIFICATION_COMMANDS
        if protocol == gate_evidence.PYTHON_GATE_PROTOCOL
    )
    command_factory = next(
        command_factory
        for protocol, command_factory, _ in gate_evidence.VERIFICATION_COMMANDS
        if protocol == gate_evidence.TARGETED_PYTHON_PROTOCOL
    )
    full_gate_command = full_gate_factory(gate_evidence.ROOT)
    command = command_factory(gate_evidence.ROOT)

    assert "-I" in full_gate_command
    assert "-m" not in command
    assert "pytest" not in command
    assert "-I" in command
    assert "scripts/pytest_runner.py" in command


def test_rust_toolchain_contract_has_one_exact_msrv() -> None:
    workspace = tomllib.loads((gate_evidence.ROOT / "Cargo.toml").read_text(encoding="utf-8"))
    toolchain = tomllib.loads((gate_evidence.ROOT / gate_evidence.RUST_TOOLCHAIN_PATH).read_text(encoding="utf-8"))[
        "toolchain"
    ]

    assert REQUIRED_RUST_VERSION == "1.88.0"
    assert workspace["workspace"]["package"]["rust-version"] == REQUIRED_RUST_VERSION
    assert toolchain["channel"] == REQUIRED_RUST_VERSION
    assert toolchain["profile"] == "minimal"
    assert {"rustfmt", "clippy"}.issubset(toolchain["components"])
    assert gate_evidence.CARGO_DESKTOP_BUILD_PROTOCOL in gate_evidence.G0A_REQUIRED_PROTOCOLS

    rust_commands = [
        command_factory(gate_evidence.ROOT)
        for protocol, command_factory, _ in gate_evidence.VERIFICATION_COMMANDS
        if protocol.startswith("cargo ")
    ]
    assert rust_commands
    assert all(command[:2] == ["cargo", f"+{REQUIRED_RUST_VERSION}"] for command in rust_commands)


def test_newer_rust_cannot_impersonate_the_msrv() -> None:
    assert gate_evidence._tool_version_matches_release(
        f"rustc {REQUIRED_RUST_VERSION} (test)",
        tool="rustc",
        required_version=REQUIRED_RUST_VERSION,
    )
    assert not gate_evidence._tool_version_matches_release(
        "rustc 1.96.0 (test)",
        tool="rustc",
        required_version=REQUIRED_RUST_VERSION,
    )
    assert not gate_evidence._tool_version_matches_release(
        "cargo 1.96.0 (test)",
        tool="cargo",
        required_version=REQUIRED_RUST_VERSION,
    )

    evidence = _passing_evidence()
    evidence["source"]["verificationRuns"][-1]["environment"]["toolchain"]["rustc"] = "rustc 1.96.0 (test)"
    with pytest.raises(ValueError, match="recorded rustc version"):
        validate_passed_decision(evidence, verify_current_workspace=False)

    evidence = _passing_evidence()
    evidence["source"]["verificationRuns"][-1]["environment"]["toolchain"]["cargo"] = "cargo 1.96.0 (test)"
    with pytest.raises(ValueError, match="recorded cargo version"):
        validate_passed_decision(evidence, verify_current_workspace=False)


def test_workspace_and_toolchain_version_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "Cargo.toml").write_text(
        """
[workspace]
members = []

[workspace.package]
rust-version = "1.88.0"
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "rust-toolchain.toml").write_text(
        """
[toolchain]
channel = "1.89.0"
profile = "minimal"
components = ["rustfmt", "clippy"]
""".lstrip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        gate_evidence,
        "_python_environment_evidence",
        lambda root: {
            "pythonInstalledDistributionsSha256": "0" * 64,
            "pythonLockStatus": "match",
            "pythonLockMismatches": [],
        },
    )
    monkeypatch.setattr(
        gate_evidence,
        "_lock_file_hashes",
        lambda root: {"Cargo.lock": "0" * 64, "poetry.lock": "0" * 64},
    )

    def fake_tool_version(root: Path, tool: str, *args: str) -> str:
        if tool == "rustc":
            return "rustc 1.89.0 (test)"
        if tool == "cargo":
            return "cargo 1.89.0 (test)"
        return "v24.0.0"

    monkeypatch.setattr(gate_evidence, "_tool_version", fake_tool_version)

    environment = gate_evidence._verification_environment(tmp_path)
    assert environment["requiredRustVersion"] == REQUIRED_RUST_VERSION
    assert environment["rustVersionMeetsWorkspace"] is False


@pytest.mark.parametrize(
    "toolchain_text",
    [
        None,
        "[toolchain\nchannel = 'not-valid-toml'\n",
    ],
    ids=["missing", "malformed"],
)
def test_gate_module_import_is_safe_before_toolchain_preflight(
    tmp_path: Path,
    toolchain_text: str | None,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    copied_generator = scripts / "generate_gate_evidence.py"
    shutil.copyfile(
        gate_evidence.ROOT / "scripts" / "generate_gate_evidence.py",
        copied_generator,
    )
    shutil.copyfile(
        gate_evidence.ROOT / "scripts" / "local_verification.py",
        scripts / "local_verification.py",
    )
    if toolchain_text is not None:
        (tmp_path / "rust-toolchain.toml").write_text(
            toolchain_text,
            encoding="utf-8",
        )

    completed = subprocess.run(
        [sys.executable, "-I", str(copied_generator), "--help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "toolchain_text",
    [
        None,
        "[toolchain\nchannel = 'not-valid-toml'\n",
    ],
    ids=["missing", "malformed"],
)
def test_broken_toolchain_replaces_an_old_pass_with_blocked_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    toolchain_text: str | None,
) -> None:
    root = _repository(tmp_path)
    (root / "Cargo.toml").write_text(
        """
[workspace]
members = []

[workspace.package]
rust-version = "1.88.0"
""".lstrip(),
        encoding="utf-8",
    )
    if toolchain_text is not None:
        (root / "rust-toolchain.toml").write_text(
            toolchain_text,
            encoding="utf-8",
        )
    evidence_path, status_path = _write_gate_outputs(
        root,
        _passing_evidence(),
        status="old passed status\n",
    )
    monkeypatch.setattr(
        gate_evidence,
        "_validate_repository_python",
        lambda root_arg: Path(sys.executable),
    )

    result = gate_evidence.generate(
        root,
        evidence_path.relative_to(root),
        status_path.relative_to(root),
        verify=True,
    )

    persisted = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result == 1
    assert persisted["decision"] == "blocked"
    assert persisted["source"].get("verificationRuns", []) == []
    assert "G0A has passed" in persisted["claims"]["forbidden"]
    assert "last_verified: not-verified" in status_path.read_text(encoding="utf-8")
    assert "old passed status" not in status_path.read_text(encoding="utf-8")
