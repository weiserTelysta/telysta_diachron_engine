"""Capture actual legacy bytes and failures, without granting migration approval.

Uses the hermetic pytest runner with --runxfail so each known defect produces
a real assertion failure. This research archive never writes Rust project state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pytest_runner import hermetic_environment, run_pytest

SCHEMA = "telysta-legacy-evidence-archive.v1"
FIXTURE = Path("tests/fixtures/legacy_replay_migration_cases_v1.json")
MANIFEST_FILES = {"manifest.json", "manifest.sha256"}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _files(root: Path) -> list[dict[str, Any]]:
    """Hash raw bytes, including native line endings. Never follow symlinks."""
    result = []
    for directory, names, files in os.walk(root, followlinks=False):
        for name in [*names, *files]:
            if (Path(directory) / name).is_symlink():
                raise ValueError(f"archive contains a symlink: {name}")
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative in MANIFEST_FILES:
                continue
            payload = path.read_bytes()
            result.append({"path": relative, "sizeBytes": len(payload), "sha256": _sha256(payload)})
    return sorted(result, key=lambda item: item["path"])


def _cases(fixture: Path) -> list[dict[str, Any]]:
    cases = json.loads(fixture.read_bytes())["cases"]
    if {case["fixtureId"] for case in cases} != {
        f"LEGACY-REPLAY-{number:03}" for number in range(1, 9)
    } or len(cases) != 8:
        raise ValueError("expected the eight distinct legacy replay cases")
    return cases


def _record_pytest_aliases(raw: Path) -> list[dict[str, str]]:
    # pytest creates sibling "...current" navigation aliases. Preserve their
    # descriptors, then remove only these aliases so the archive is portable.
    aliases = []
    for path in raw.iterdir():
        if not path.is_symlink():
            continue
        target = path.resolve(strict=True)
        if not path.name.endswith("current") or target.parent != raw or not target.is_dir():
            raise ValueError(f"unexpected pytest artifact symlink: {path}")
        aliases.append({"path": path.name, "target": os.readlink(path)})
        path.unlink()
    return sorted(aliases, key=lambda item: item["path"])


def _failure(report: Path, node_id: str) -> dict[str, str]:
    testcases = list(ET.parse(report).getroot().iter("testcase"))
    if len(testcases) != 1:
        raise ValueError("legacy capture must execute exactly one test per case")
    testcase = testcases[0]
    actual_id = testcase.attrib["classname"].replace(".", "/") + ".py::" + testcase.attrib["name"]
    failures = testcase.findall("failure")
    if (actual_id != node_id or len(failures) != 1
            or testcase.find("skipped") is not None or testcase.find("error") is not None):
        raise ValueError(f"expected a real failure from {node_id}")
    failure = failures[0]
    identity = {
        "nodeId": node_id,
        "message": failure.get("message", ""),
        "type": failure.get("type", ""),
    }
    return {**identity, "fingerprintSha256": _sha256(_json_bytes(identity))}


def _git(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True,
    ).stdout


def capture_archive(destination: Path) -> dict[str, Any]:
    """Create an exclusive archive. Incomplete runs have no passing manifest."""
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    source_revision = _git("rev-parse", "HEAD").decode().strip()
    sources = destination / "sources"
    tracked = _git(
        "ls-files", "--cached", "--others", "--exclude-standard", "-z",
        "app", "data", "scripts", "tests", "pyproject.toml", "poetry.lock",
    )
    source_paths = {Path(os.fsdecode(name)) for name in tracked.split(b"\0") if name}
    source_paths.add(Path(__file__).resolve().relative_to(ROOT))
    for relative in sorted(source_paths):
        source = ROOT / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"cannot archive non-regular source: {relative}")
        target = sources / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (destination / "tracked-changes.patch").write_bytes(_git("diff", "--binary", "HEAD"))

    results = []
    for case in _cases(sources / FIXTURE):
        directory = destination / "cases" / case["fixtureId"]
        directory.mkdir(parents=True)
        node_id = case["sourceTestNodeId"]
        run = run_pytest(
            [node_id, "--runxfail", "--basetemp", str(directory / "raw"),
             "--junitxml", str(directory / "failure.xml"), "-q", "--tb=short"],
            capture_output=True,
        )
        (directory / "stdout.txt").write_bytes((run.stdout or "").encode("utf-8"))
        (directory / "stderr.txt").write_bytes((run.stderr or "").encode("utf-8"))
        if (run.pytest_returncode, run.returncode, run.collected, run.executed) != (1, 1, 1, 1):
            raise ValueError(f"{node_id} did not produce exactly one executed failure: {run.summary()}")
        (directory / "pytest-aliases.json").write_bytes(
            _json_bytes(_record_pytest_aliases(directory / "raw"))
        )
        results.append({
            "fixtureId": case["fixtureId"],
            "command": list(run.command),
            "collected": run.collected,
            "executed": run.executed,
            "pytestExitCode": run.pytest_returncode,
            "failure": _failure(directory / "failure.xml", node_id),
            "rawFiles": [item["path"] for item in _files(directory / "raw")],
        })

    golden = destination / "golden"
    golden.mkdir()
    command = [sys.executable, "-I", str(Path(__file__).resolve()), "--_golden-child", str(golden)]
    completed = subprocess.run(command, cwd=ROOT, env=hermetic_environment(), capture_output=True)
    (golden / "stdout.txt").write_bytes(completed.stdout)
    (golden / "stderr.txt").write_bytes(completed.stderr)
    if completed.returncode:
        raise ValueError(f"legacy golden capture failed with exit {completed.returncode}")

    for relative in source_paths:
        if (ROOT / relative).is_symlink() or (ROOT / relative).read_bytes() != (sources / relative).read_bytes():
            raise ValueError(f"source changed during capture: {relative}")
    if (_git("rev-parse", "HEAD").decode().strip() != source_revision
            or _git("diff", "--binary", "HEAD") != (destination / "tracked-changes.patch").read_bytes()):
        raise ValueError("Git subject changed during capture")

    manifest = {
        "schemaVersion": SCHEMA,
        "status": "local_capture_not_reviewed_or_frozen",
        "scope": "legacy_research_evidence_not_rust_state_or_gate_attestation",
        "timestampUtc": datetime.now(timezone.utc).isoformat(),
        "sourceRevision": source_revision,
        "reviewedSubjectCommit": None,
        "trackedDirty": bool(_git("diff", "--name-only", "HEAD")),
        "environment": {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "lineSeparatorHex": os.linesep.encode().hex(),
        },
        "cases": results,
        "goldenCommand": command,
        "files": _files(destination),
    }
    payload = _json_bytes(manifest)
    (destination / "manifest.json").write_bytes(payload)
    (destination / "manifest.sha256").write_text(_sha256(payload) + "\n", encoding="ascii")
    verify_archive(destination)
    return manifest


def verify_archive(root: Path) -> dict[str, Any]:
    """Check byte integrity and exact failure coverage; this cannot approve a gate."""
    if root.is_symlink() or any((root / name).is_symlink() for name in MANIFEST_FILES):
        raise ValueError("archive root and manifest must not be symlinks")
    payload = (root / "manifest.json").read_bytes()
    if _sha256(payload) != (root / "manifest.sha256").read_text(encoding="ascii").strip():
        raise ValueError("manifest checksum mismatch")
    manifest = json.loads(payload)
    if manifest.get("schemaVersion") != SCHEMA or manifest.get("status") != "local_capture_not_reviewed_or_frozen":
        raise ValueError("unsupported evidence schema or review claim")
    if manifest.get("scope") != "legacy_research_evidence_not_rust_state_or_gate_attestation":
        raise ValueError("unsupported evidence authority claim")
    if manifest.get("reviewedSubjectCommit") is not None:
        raise ValueError("this capture tool cannot assert independent review")
    if manifest["files"] != _files(root):
        raise ValueError("archive file manifest does not match raw bytes")
    cases = _cases(root / "sources" / FIXTURE)
    if len(manifest["cases"]) != len(cases):
        raise ValueError("incomplete failure coverage")
    for expected, actual in zip(cases, manifest["cases"], strict=True):
        directory = root / "cases" / expected["fixtureId"]
        if actual["fixtureId"] != expected["fixtureId"]:
            raise ValueError("failure case identity mismatch")
        if (actual["collected"], actual["executed"], actual["pytestExitCode"]) != (1, 1, 1):
            raise ValueError("failure did not execute exactly one test")
        if actual["failure"] != _failure(directory / "failure.xml", expected["sourceTestNodeId"]):
            raise ValueError("failure fingerprint mismatch")
        if actual["rawFiles"] != [item["path"] for item in _files(directory / "raw")]:
            raise ValueError("case raw artifact manifest mismatch")
    baseline = json.loads((root / "sources/tests/fixtures/golden/legacy_v1.json").read_bytes())
    reports = json.loads((root / "golden/report.json").read_bytes())
    if len(reports) != len(baseline["scenarios"]) or {
        report["name"] for report in reports
    } != set(baseline["scenarios"]):
        raise ValueError("incomplete golden capture")
    for report in reports:
        expected = baseline["scenarios"][report["name"]]
        actual = report["report"]
        if report["seed"] != baseline["seed"] or any(
            actual["hashes"][field] != expected[field] for field in ("domains", "full")
        ) or actual["hard_errors"] != expected["hard_errors"]:
            raise ValueError(f"legacy golden characterization changed: {report['name']}")
    return manifest


def _golden_child(destination: Path) -> None:
    from app.engine.golden import GOLDEN_SCENARIOS, run_legacy_golden_scenario

    reports = [
        run_legacy_golden_scenario(name, 888, destination / name)
        for name in GOLDEN_SCENARIOS
    ]
    (destination / "report.json").write_bytes(_json_bytes(reports))


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--_golden-child":
        _golden_child(Path(sys.argv[2]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="new archive directory; never overwrites")
    group.add_argument("--verify", type=Path, help="verify an existing local archive")
    args = parser.parse_args()
    try:
        manifest = verify_archive(args.verify) if args.verify else capture_archive(args.output)
    except (OSError, ValueError, KeyError, ET.ParseError, subprocess.SubprocessError) as error:
        print(f"Legacy evidence capture/verification failed: {error}", file=sys.stderr)
        return 1
    print(f"{manifest['status']}: {len(manifest['cases'])} failures; {len(manifest['files'])} files verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
