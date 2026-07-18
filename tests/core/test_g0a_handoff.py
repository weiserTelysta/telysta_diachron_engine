"""Tests for the G0A review and clean-baseline handoff report."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from scripts.g0a_handoff import (
    ATTESTATION_ONLY_PATHS,
    REVIEW_TARGETS,
    SCHEMA_VERSION,
    WorktreeEntry,
    build_report,
    is_transient_path,
    needs_manual_change_review,
    parse_porcelain_v2_z,
    render_summary,
)


ROOT = Path(__file__).resolve().parents[2]


def test_porcelain_parser_preserves_status_paths_and_rename_identity() -> None:
    payload = (
        b"1 .M N... 100644 100644 100644 "
        b"0123456789012345678901234567890123456789 "
        b"0123456789012345678901234567890123456789 tracked.txt\0"
        b"? untracked file.txt\0"
        b"2 R. N... 100644 100644 100644 "
        b"0123456789012345678901234567890123456789 "
        b"0123456789012345678901234567890123456789 R100 new.txt\0old.txt\0"
    )

    entries = parse_porcelain_v2_z(payload)

    assert [(entry.status, entry.path) for entry in entries] == [
        ("R.", "new.txt"),
        (".M", "tracked.txt"),
        ("??", "untracked file.txt"),
    ]
    renamed = entries[0]
    assert renamed.record_kind == "rename_or_copy"
    assert renamed.original_path == "old.txt"


def test_transient_and_cleanup_sensitive_changes_are_not_routine_candidates() -> None:
    for path in (
        "target/debug/telysta.exe",
        ".venv/Lib/site-packages/x.py",
        "app/__pycache__/module.pyc",
        "web/node_modules/pkg/index.js",
        "logs/gate.log",
        "scratch.tmp",
    ):
        assert is_transient_path(path)

    assert not is_transient_path("crates/telysta-core/src/state.rs")
    assert needs_manual_change_review(WorktreeEntry("ordinary", ".D", "legacy.py"))
    assert needs_manual_change_review(
        WorktreeEntry("rename_or_copy", "R.", "new.py", "old.py")
    )
    assert needs_manual_change_review(WorktreeEntry("unmerged", "UU", "conflict.py"))
    assert not needs_manual_change_review(
        WorktreeEntry("ordinary", ".M", "crates/telysta-core/src/state.rs")
    )


def test_current_handoff_report_partitions_every_entry_and_hashes_review_inputs() -> None:
    report = build_report(ROOT)

    assert report["schemaVersion"] == SCHEMA_VERSION
    assert report["purpose"] == "preparation_only_not_an_approval_or_gate_decision"
    assert report["readiness"]["independentApprovalRecorded"] is False
    assert report["readiness"]["cleanSubjectReadyForVerification"] is (
        report["readiness"]["subjectReadyForStagingReview"]
        and not report["subjectCandidates"]
    )
    assert report["missingReviewTargets"] == []
    assert (
        report["counts"]["trackedTransientEntries"]
        == len(report["trackedTransient"])
    )

    subject_paths = {entry["path"] for entry in report["subjectCandidates"]}
    attestation_paths = {entry["path"] for entry in report["attestationOnly"]}
    assert subject_paths.isdisjoint(attestation_paths)
    assert attestation_paths <= ATTESTATION_ONLY_PATHS
    assert (
        len(subject_paths) + len(attestation_paths)
        == report["counts"]["allWorktreeEntries"]
    )

    expected_targets = {path for _kind, path in REVIEW_TARGETS}
    actual_targets = {target["path"] for target in report["reviewTargets"]}
    assert actual_targets == expected_targets
    for target in report["reviewTargets"]:
        path = ROOT / target["path"]
        assert target["exists"] is True
        assert target["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_untracked_seed_remains_subject_until_first_commit(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
    )
    for _kind, relative in REVIEW_TARGETS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("review input\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "review inputs"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    for relative in ATTESTATION_ONLY_PATHS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("blocked seed\n", encoding="utf-8")

    bootstrap = build_report(tmp_path)
    assert {
        entry["path"] for entry in bootstrap["bootstrapSubject"]
    } == ATTESTATION_ONLY_PATHS
    assert bootstrap["readiness"]["cleanSubjectReadyForVerification"] is False

    subprocess.run(
        ["git", "add", *sorted(ATTESTATION_ONLY_PATHS)],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "blocked seed"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    status_path = tmp_path / "docs/STATUS.md"
    status_path.write_text("regenerated status\n", encoding="utf-8")

    attestation = build_report(tmp_path)
    assert {
        entry["path"] for entry in attestation["attestationOnly"]
    } == {"docs/STATUS.md"}
    assert attestation["subjectCandidates"] == []
    assert attestation["readiness"]["cleanSubjectReadyForVerification"] is True


def test_summary_refuses_to_imply_approval() -> None:
    report = build_report(ROOT)
    summary = render_summary(report)
    assert "independent approval recorded by this tool: false" in summary
    clean_subject = str(
        report["readiness"]["cleanSubjectReadyForVerification"]
    ).lower()
    assert f"clean subject ready: {clean_subject}" in summary
