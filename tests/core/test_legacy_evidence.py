"""Real legacy failures and raw archive integrity, without migration approval."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from scripts.legacy_evidence import capture_archive, verify_archive


@pytest.fixture(scope="module")
def archive(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("legacy-evidence") / "capture"
    capture_archive(path)
    return path


def _rewrite_manifest(path: Path, payload: dict) -> None:
    raw = json.dumps(payload, sort_keys=True).encode()
    (path / "manifest.json").write_bytes(raw)
    (path / "manifest.sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n")


def test_capture_reproduces_eight_defects_and_preserves_illegal_golden_forms(archive: Path) -> None:
    manifest = verify_archive(archive)
    assert manifest["reviewedSubjectCommit"] is None
    assert manifest["status"] == "local_capture_not_reviewed_or_frozen"
    assert len(manifest["cases"]) == 8
    for case in manifest["cases"]:
        assert (case["collected"], case["executed"], case["pytestExitCode"]) == (1, 1, 1)
        assert case["failure"]["message"].startswith(("AssertionError:", "AttributeError:"))
        assert "--runxfail" in case["command"]
    # The decoder-only case does not persist files; do not invent a raw event.
    assert manifest["cases"][3]["rawFiles"] == []
    keyframes = [file for file in manifest["files"] if "keyframe_era_" in file["path"]]
    assert keyframes
    reports = json.loads((archive / "golden/report.json").read_bytes())
    assert len(reports) == 5
    assert all(report["report"]["phonology"]["illegal_forms"] > 0 for report in reports)
    assert not (archive / "project.json").exists()


@pytest.mark.parametrize("mutation", ["tamper", "delete", "extra", "manifest", "review", "coverage"])
def test_archive_verification_rejects_corruption_and_false_claims(
    archive: Path, tmp_path: Path, mutation: str,
) -> None:
    copy = tmp_path / "copy"
    shutil.copytree(archive, copy)
    if mutation == "tamper":
        next(copy.glob("cases/*/raw/**/keyframe_era_*.json")).write_bytes(b"{}")
    elif mutation == "delete":
        (copy / "golden/report.json").unlink()
    elif mutation == "extra":
        (copy / "unexpected.txt").write_bytes(b"unlisted")
    elif mutation == "manifest":
        (copy / "manifest.json").write_bytes(b"{}")
    else:
        manifest = json.loads((copy / "manifest.json").read_bytes())
        if mutation == "review":
            manifest["reviewedSubjectCommit"] = "fabricated-review"
        else:
            manifest["cases"] = manifest["cases"][:-1]
        _rewrite_manifest(copy, manifest)
    with pytest.raises(ValueError):
        verify_archive(copy)


def test_capture_refuses_to_overwrite_existing_archive(archive: Path) -> None:
    before = (archive / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        capture_archive(archive)
    assert (archive / "manifest.json").read_bytes() == before


def test_unexpected_pass_cannot_publish_a_complete_archive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from scripts.pytest_runner import PytestRunResult

    monkeypatch.setattr(
        "scripts.legacy_evidence.run_pytest",
        lambda *args, **kwargs: PytestRunResult((), 0, 0, 1, 1, None, "unexpected pass", ""),
    )
    output = tmp_path / "incomplete"
    with pytest.raises(ValueError, match="exactly one executed failure"):
        capture_archive(output)
    assert not (output / "manifest.json").exists()
    assert "unexpected pass" in next(output.glob("cases/*/stdout.txt")).read_text()
