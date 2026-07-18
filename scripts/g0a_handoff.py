"""Prepare a deterministic G0A review and clean-baseline handoff report.

This tool does not approve an ADR, assign a human, create a commit, or change
GateEvidence.  It makes the current review inputs and worktree partition
explicit so a reviewer can reproduce the handoff without relying on a meeting
or an operator-curated file list.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "telysta-g0a-handoff-report.v1"
ATTESTATION_ONLY_PATHS = frozenset(
    {
        "docs/G0A_GATE_EVIDENCE_2026-07-17.json",
        "docs/STATUS.md",
    }
)
REVIEW_TARGETS = (
    ("architecture-decision", "docs/adr/ADR-011-project-manifest-run-ledger-job-identity.md"),
    ("architecture-decision", "docs/adr/ADR-012-project-package-commit-authority.md"),
    (
        "architecture-decision",
        "docs/adr/ADR-013-rng-compatibility-and-distribution-versioning.md",
    ),
    ("architecture-contract", "docs/PLATFORM_CONTRACT_PACK_V1.md"),
    ("gate-policy", "docs/G0A_POLICY_V1.json"),
    ("gate-schema", "docs/GATE_EVIDENCE_MANIFEST_V2.schema.json"),
    ("gate-model", "docs/governance/GATE_EVIDENCE_MODEL_V2.md"),
    ("determinism-fixture", "tests/fixtures/rng_known_answers_v1.json"),
)
TRANSIENT_SEGMENTS = frozenset(
    {
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "htmlcov",
        "logs",
        "node_modules",
        "target",
    }
)
TRANSIENT_SUFFIXES = (
    ".log",
    ".pyc",
    ".pyo",
    ".tmp",
    ".swp",
)


@dataclass(frozen=True)
class WorktreeEntry:
    """One Git porcelain v2 worktree entry."""

    record_kind: str
    status: str
    path: str
    original_path: str | None = None

    def as_dict(self) -> dict[str, str]:
        result = {
            "recordKind": self.record_kind,
            "status": self.status,
            "path": self.path,
        }
        if self.original_path is not None:
            result["originalPath"] = self.original_path
        return result


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def _decode_path(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogateescape").replace("\\", "/")


def parse_porcelain_v2_z(payload: bytes) -> list[WorktreeEntry]:
    """Parse the path-bearing records emitted by ``git status --porcelain=v2 -z``."""

    records = payload.split(b"\0")
    entries: list[WorktreeEntry] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        prefix = record[:2]
        if prefix == b"? ":
            entries.append(WorktreeEntry("untracked", "??", _decode_path(record[2:])))
            continue
        if prefix == b"! ":
            continue
        if prefix == b"1 ":
            fields = record.split(b" ", 8)
            if len(fields) != 9:
                raise ValueError("invalid ordinary porcelain v2 record")
            entries.append(
                WorktreeEntry("ordinary", fields[1].decode("ascii"), _decode_path(fields[8]))
            )
            continue
        if prefix == b"2 ":
            fields = record.split(b" ", 9)
            if len(fields) != 10 or index >= len(records):
                raise ValueError("invalid rename/copy porcelain v2 record")
            original_path = _decode_path(records[index])
            index += 1
            entries.append(
                WorktreeEntry(
                    "rename_or_copy",
                    fields[1].decode("ascii"),
                    _decode_path(fields[9]),
                    original_path,
                )
            )
            continue
        if prefix == b"u ":
            fields = record.split(b" ", 10)
            if len(fields) != 11:
                raise ValueError("invalid unmerged porcelain v2 record")
            entries.append(
                WorktreeEntry("unmerged", fields[1].decode("ascii"), _decode_path(fields[10]))
            )
            continue
        if record.startswith(b"# "):
            continue
        raise ValueError(f"unsupported porcelain v2 record: {record[:20]!r}")
    return sorted(entries, key=lambda entry: (entry.path, entry.status))


def worktree_entries(root: Path = ROOT) -> list[WorktreeEntry]:
    payload = _git(
        root,
        "status",
        "--porcelain=v2",
        "-z",
        "--untracked-files=all",
    )
    return parse_porcelain_v2_z(payload)


def tracked_paths(root: Path = ROOT) -> set[str]:
    payload = _git(root, "ls-files", "-z")
    return {
        _decode_path(path)
        for path in payload.split(b"\0")
        if path
    }


def is_transient_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    segments = {segment.casefold() for segment in normalized.split("/")}
    lower = normalized.casefold()
    return bool(segments & TRANSIENT_SEGMENTS) or lower.endswith(TRANSIENT_SUFFIXES)


def needs_manual_change_review(entry: WorktreeEntry) -> bool:
    """Flag changes that the cleanup contract forbids treating as routine staging."""

    return (
        entry.record_kind in {"rename_or_copy", "unmerged"}
        or "D" in entry.status
        or "U" in entry.status
    )


def _front_matter(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    parsed = yaml.safe_load("\n".join(lines[1:end]))
    return parsed if isinstance(parsed, dict) else None


def _review_target(root: Path, kind: str, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        return {
            "kind": kind,
            "path": relative,
            "exists": False,
        }
    result: dict[str, Any] = {
        "kind": kind,
        "path": relative,
        "exists": True,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    metadata = _front_matter(path) if path.suffix.casefold() == ".md" else None
    if metadata is not None:
        result["decisionStatus"] = metadata.get("decision_status")
        result["implementationStatus"] = metadata.get("implementation_status")
        result["owner"] = metadata.get("owner")
        result["reviewers"] = metadata.get("reviewers")
    return result


def build_report(root: Path = ROOT) -> dict[str, Any]:
    entries = worktree_entries(root)
    tracked = tracked_paths(root)
    attestation = [
        entry
        for entry in entries
        if entry.path in ATTESTATION_ONLY_PATHS
        and entry.path in tracked
        and not needs_manual_change_review(entry)
    ]
    subject = [
        entry for entry in entries if entry not in attestation
    ]
    transient = [entry for entry in entries if is_transient_path(entry.path)]
    tracked_transient = sorted(path for path in tracked if is_transient_path(path))
    manual = [entry for entry in subject if needs_manual_change_review(entry)]
    targets = [_review_target(root, kind, path) for kind, path in REVIEW_TARGETS]
    missing_targets = [target["path"] for target in targets if not target["exists"]]
    missing_bootstrap = sorted(
        path for path in ATTESTATION_ONLY_PATHS if not (root / path).is_file()
    )
    bootstrap_subject = [
        entry
        for entry in subject
        if entry.path in ATTESTATION_ONLY_PATHS and entry.path not in tracked
    ]
    subject_ready_for_review = (
        not transient
        and not tracked_transient
        and not manual
        and not missing_targets
        and not missing_bootstrap
    )
    clean_subject_ready = subject_ready_for_review and not subject

    base_commit = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    base_tree = _git(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "purpose": "preparation_only_not_an_approval_or_gate_decision",
        "baseCommit": base_commit,
        "baseTree": base_tree,
        "counts": {
            "allWorktreeEntries": len(entries),
            "subjectCandidateEntries": len(subject),
            "attestationOnlyEntries": len(attestation),
            "bootstrapSubjectEntries": len(bootstrap_subject),
            "transientEntries": len(transient),
            "trackedTransientEntries": len(tracked_transient),
            "manualChangeReviewEntries": len(manual),
            "missingReviewTargets": len(missing_targets),
            "missingBootstrapPaths": len(missing_bootstrap),
        },
        "readiness": {
            "subjectReadyForStagingReview": subject_ready_for_review,
            "cleanSubjectReadyForVerification": clean_subject_ready,
            "independentApprovalRecorded": False,
        },
        "subjectCandidates": [entry.as_dict() for entry in subject],
        "attestationOnly": [entry.as_dict() for entry in attestation],
        "bootstrapSubject": [entry.as_dict() for entry in bootstrap_subject],
        "rejectedTransient": [entry.as_dict() for entry in transient],
        "trackedTransient": tracked_transient,
        "manualChangeReview": [entry.as_dict() for entry in manual],
        "missingReviewTargets": missing_targets,
        "missingBootstrapPaths": missing_bootstrap,
        "reviewTargets": targets,
    }


def render_summary(report: dict[str, Any]) -> str:
    counts = report["counts"]
    readiness = report["readiness"]
    return "\n".join(
        (
            f"G0A handoff subject: {report['baseCommit']} ({report['baseTree']})",
            (
                "worktree: "
                f"{counts['subjectCandidateEntries']} subject candidates, "
                f"{counts['attestationOnlyEntries']} attestation-only, "
                f"{counts['bootstrapSubjectEntries']} bootstrap-subject, "
                f"{counts['transientEntries']} transient, "
                f"{counts['trackedTransientEntries']} tracked-transient, "
                f"{counts['manualChangeReviewEntries']} manual-review"
            ),
            (
                "staging review ready: "
                f"{str(readiness['subjectReadyForStagingReview']).lower()}"
            ),
            (
                "clean subject ready: "
                f"{str(readiness['cleanSubjectReadyForVerification']).lower()}"
            ),
            "independent approval recorded by this tool: false",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail on transient, destructive/ambiguous changes, or missing review inputs",
    )
    parser.add_argument(
        "--require-clean-subject",
        action="store_true",
        help="also fail until no subject-candidate worktree changes remain",
    )
    args = parser.parse_args(argv)

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_summary(report))

    if args.check and not report["readiness"]["subjectReadyForStagingReview"]:
        return 1
    if args.require_clean_subject and not report["readiness"]["cleanSubjectReadyForVerification"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
