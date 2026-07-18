"""Evidence generation must be reproducible and must not self-reference."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.generate_gate_evidence as gate_evidence
from scripts.generate_gate_evidence import (
    ADR_EXECUTABLE_CLAIM,
    FINGERPRINT_SCHEMA,
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
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "baseline")
    return tmp_path


@pytest.fixture
def ignore_gate_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate_evidence, "_gate_policy_issues", lambda evidence, root: [])


def _evidence() -> dict[str, Any]:
    software = [
        {
            "kind": "SoftwareVerificationEvidence",
            "path": "placeholder",
            "protocol": protocol,
            "result": "pass",
            "details": "old result",
            "verificationMode": "direct",
            "executedCommand": protocol,
        }
        for protocol in G0A_REQUIRED_PROTOCOL_ORDER
    ]
    other_evidence = [
        {
            "kind": kind,
            "path": "README.md",
            "sha256": "0" * 64,
            "result": "pass",
        }
        for kind in (
            "ArchitectureContractEvidence",
            "ArchitectureDecisionEvidence",
            "DeterminismEvidence",
        )
    ]
    return {
        "$schema": "GATE_EVIDENCE_MANIFEST_V2.schema.json",
        "schemaVersion": "telysta-gate-evidence-manifest.v2",
        "gateId": "G0A",
        "gateName": "test",
        "decision": "blocked",
        "decisionDate": "2026-07-17",
        "source": {},
        "claims": {
            "allowed": [
                ADR_EXECUTABLE_CLAIM,
                PLATFORM_REVIEW_CLAIM,
                RNG_VERIFIED_CLAIM,
                (
                    "the recorded dirty "
                    f"{WORKTREE_VERIFICATION_CLAIM_SUFFIX}"
                ),
            ],
            "forbidden": ["G0A has passed"],
        },
        "evidence": software + other_evidence,
        "requirements": [
            {
                "id": requirement_id,
                "name": f"requirement {requirement_id}",
                "status": "failed",
                "evidencePaths": [],
            }
            for requirement_id in sorted(G0A_REQUIRED_REQUIREMENT_IDS)
        ],
        "blockers": [
            {"severity": "blocking", "id": "G0A-B01", "summary": "blocked"}
        ],
        "owner": None,
        "reviewers": [],
        "waivers": [],
        "expiresWhen": ["contract changes"],
        "nextDecision": "review",
    }


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
    assert not any(
        claim.endswith(WORKTREE_VERIFICATION_CLAIM_SUFFIX)
        for claim in first["claims"]["allowed"]
    )
    assert all(
        item["result"] == "not_run_for_fingerprint"
        for item in first["evidence"]
        if item["kind"] == "SoftwareVerificationEvidence"
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
    with pytest.raises(ValueError, match="cannot claim passed"):
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
        "environment": "test",
        "verificationRuns": [
            {
                "runId": "gate-run:" + ("1" * 32),
                "subjectCommit": "a" * 40,
                "subjectTree": "b" * 40,
                "startedAt": "2026-07-17T04:29:00Z",
                "finishedAt": "2026-07-17T04:30:00Z",
                "result": "pass",
                "protocols": list(G0A_REQUIRED_PROTOCOL_ORDER),
                "environment": {
                    "platform": "test",
                    "pythonExecutable": "python",
                    "pythonVersion": "test",
                    "pythonInstalledDistributionsSha256": "0" * 64,
                    "pythonLockStatus": "match",
                    "pythonLockMismatches": [],
                    "rustcVersion": "test",
                    "cargoVersion": "test",
                    "requiredRustVersion": REQUIRED_RUST_VERSION,
                    "rustVersionMeetsWorkspace": True,
                    "nodeVersion": "test",
                    "lockFileSha256": {
                        "Cargo.lock": "0" * 64,
                        "poetry.lock": "0" * 64,
                    },
                },
            }
        ],
    }
    for requirement in evidence["requirements"]:
        requirement["status"] = "passed"
    evidence["blockers"] = []
    evidence["owner"] = {
        "provider": "test",
        "stableAccountId": "account:owner",
        "login": "owner",
        "displayName": "Owner",
        "role": "code-owner",
    }
    evidence["reviewers"] = [
        {
            "provider": "test",
            "stableAccountId": "account:reviewer",
            "login": "reviewer",
            "displayName": "Independent Reviewer",
            "roles": ["architecture", "migration"],
            "reviewedSubjectCommit": "a" * 40,
            "reviewedSubjectTree": "b" * 40,
            "reviewUrl": "https://example.invalid/reviews/1",
            "reviewId": "review:1",
            "decision": "accepted",
            "reviewedAt": "2026-07-17T04:29:00Z",
            "conflictOfInterest": False,
        }
    ]
    evidence["claims"]["forbidden"] = []
    evidence["claims"]["allowed"].append("G0A has passed")
    for item in evidence["evidence"]:
        if item["kind"] != "SoftwareVerificationEvidence":
            continue
        item["verificationMode"] = "direct"
        item["executedCommand"] = item["protocol"]
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
    stale["evidence"][0]["result"] = "not_run_for_fingerprint"
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
        {
            "requirementId": "R0A-05",
            "approvedBy": "Reviewer",
            "reason": "test",
            "expiresAt": "2026-07-17",
        }
    ]
    invalid_cases.append(expired_waiver)

    orphan_waiver = _passing_evidence()
    orphan_waiver["waivers"] = [
        {
            "requirementId": "R0A-05",
            "approvedBy": "Reviewer",
            "reason": "test",
            "expiresAt": "2026-07-18",
        }
    ]
    invalid_cases.append(orphan_waiver)

    for invalid in invalid_cases:
        with pytest.raises(ValueError, match="GateEvidence"):
            validate_passed_decision(
                invalid,
                verify_current_workspace=False,
            )


def test_worktree_claim_tracks_clean_or_dirty_source() -> None:
    evidence = _evidence()
    _set_verified_worktree_claims(evidence, verified=True, dirty=False)
    assert (
        f"the recorded clean {WORKTREE_VERIFICATION_CLAIM_SUFFIX}"
        in evidence["claims"]["allowed"]
    )
    assert not any(
        "dirty worktree passes" in claim for claim in evidence["claims"]["allowed"]
    )


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
        lambda root: {
            "pythonLockStatus": "match",
            "pythonLockMismatches": [],
            "rustVersionMeetsWorkspace": True,
        },
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
        "covered-test": "not_run_for_fingerprint",
        "gate-two": "fail",
        "gate-three": "not_run_for_fingerprint",
    }
    assert evidence["source"]["verificationRuns"][0]["result"] == "fail"
    assert (
        evidence["source"]["verificationRuns"][0]["environment"]["pythonLockStatus"]
        == "match"
    )


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
    software = [
        item
        for item in evidence["evidence"]
        if item["kind"] == "SoftwareVerificationEvidence"
    ]
    assert software[0]["result"] == "fail"
    assert software[0]["verificationMode"] == "not_run"
    assert all(
        item["result"] == "not_run_for_fingerprint" for item in software[1:]
    )
    assert evidence["source"]["verificationRuns"] == []


def test_verified_at_requires_iso_and_verify_mode() -> None:
    assert (
        _validated_verified_at("2026-07-17T04:30:00Z")
        == "2026-07-17T04:30:00Z"
    )
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
        item
        for item in missing_protocol["evidence"]
        if item.get("protocol") != TARGETED_RNG_RUST_PROTOCOL
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
    (root / "docs").mkdir()
    (root / "docs/G0A_GATE_EVIDENCE_2026-07-17.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (root / "docs/STATUS.md").write_text("status\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "attest subject")

    assert _subject_attestation_issues({"source": source}, root=root) == []

    (root / "README.md").write_text("changed after attestation\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "change source")
    assert any(
        "non-generated paths" in issue
        for issue in _subject_attestation_issues({"source": source}, root=root)
    )


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
    evidence["source"]["verificationRuns"][0]["environment"][
        "lockFileSha256"
    ] = lock_hashes

    assert _subject_content_issues(evidence, root=root) == []

    evidence["evidence"][-1]["sha256"] = "0" * 64
    assert any(
        "hashed evidence differs" in issue
        for issue in _subject_content_issues(evidence, root=root)
    )
    evidence["evidence"][-1]["sha256"] = readme_hash

    evidence["source"]["verificationRuns"][0]["environment"]["lockFileSha256"][
        "Cargo.lock"
    ] = "0" * 64
    assert any(
        "lock-file hashes differ" in issue
        for issue in _subject_content_issues(evidence, root=root)
    )


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
    assert migrated["schemaVersion"] == "telysta-gate-evidence-manifest.v2"
    assert migrated["decision"] == "blocked"
    assert "G0A has passed" in migrated["claims"]["forbidden"]
    assert all(
        item["result"] == "not_run_for_fingerprint"
        for item in migrated["evidence"]
        if item["kind"] == "SoftwareVerificationEvidence"
    )


def test_gate_policy_rejects_proposed_architecture_decisions() -> None:
    evidence = json.loads(
        (gate_evidence.ROOT / gate_evidence.DEFAULT_EVIDENCE_PATH).read_text(
            encoding="utf-8"
        )
    )
    issues = _gate_policy_issues(evidence, root=gate_evidence.ROOT)
    assert any("ADR-011" in issue and "got proposed" in issue for issue in issues)
    assert any("ADR-012" in issue and "got proposed" in issue for issue in issues)
    assert any("ADR-013" in issue and "got proposed" in issue for issue in issues)


def test_waiver_is_checked_against_current_time(
    ignore_gate_policy: None,
) -> None:
    evidence = _passing_evidence()
    requirement_id = evidence["requirements"][0]["id"]
    evidence["requirements"][0]["status"] = "waived"
    evidence["waivers"] = [
        {
            "requirementId": requirement_id,
            "approvedBy": "Independent Reviewer",
            "reason": "temporary",
            "expiresAt": "2026-07-18T00:00:00Z",
        }
    ]
    with pytest.raises(ValueError, match="waiver is expired"):
        validate_passed_decision(
            evidence,
            verify_current_workspace=False,
            now=datetime(2026, 7, 19, tzinfo=timezone.utc),
        )


def test_required_check_does_not_share_a_fixed_pytest_basetemp() -> None:
    check_source = (gate_evidence.ROOT / "scripts/check.py").read_text(
        encoding="utf-8"
    )
    assert "--basetemp" not in check_source
    assert ".venv/pytest-tmp" not in check_source
