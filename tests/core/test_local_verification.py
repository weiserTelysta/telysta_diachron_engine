"""Adversarial local diagnostic checks; no Gate acceptance is produced here."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.local_verification import LocalRunRecorder, check_bundle


@pytest.fixture
def local_run(tmp_path: Path) -> tuple[LocalRunRecorder, dict, list]:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("target/\n", encoding="utf-8")
    locks = {name: hashlib.sha256(name.encode()).hexdigest() for name in ("Cargo.lock", "poetry.lock")}
    source = {
        "tree": "a" * 40, "lockFileSha256": locks,
        "fingerprint": {"base_commit": "b" * 40, "dirty": False,
                        "status_entry_count": 0, "sha256": "c" * 64},
    }
    command = [sys.executable, "-I", "-c", "import os; os.write(1,b'out\\xff'); os.write(2,b'err\\x00')"]
    plan = [{"protocol": "fixed-test-command", "argv": command}]
    recorder = LocalRunRecorder(tmp_path, source, plan)
    recorder.environment({"lockFileSha256": locks, "pythonLockStatus": "match"})
    return recorder, source, plan


def _pass(recorder: LocalRunRecorder, source: dict, plan: list) -> None:
    assert recorder.run(plan[0]["protocol"], plan[0]["argv"]).returncode == 0
    recorder.finish(0, source)


def _edit(recorder: LocalRunRecorder, change) -> None:
    value = json.loads((recorder.path / "manifest.json").read_text(encoding="utf-8"))
    change(value)
    (recorder.path / "manifest.json").write_text(json.dumps(value), encoding="utf-8")


def test_raw_stdout_stderr_bytes_and_exclusive_runs(local_run) -> None:
    recorder, source, plan = local_run
    _pass(recorder, source, plan)
    assert (recorder.path / "00.log").read_bytes() == b"out\xfferr\x00"
    assert check_bundle(recorder.path, plan, source, recorder.root, frozenset({"lockFileSha256", "pythonLockStatus"}))["result"] == "passed"
    other = LocalRunRecorder(recorder.root, source, plan)
    assert recorder.path != other.path
    assert (recorder.path / "00.log").read_bytes() == b"out\xfferr\x00"


@pytest.mark.parametrize("failure", ["exit", "launch", "interrupt"])
def test_failed_or_interrupted_command_is_never_a_pass(local_run, monkeypatch, failure) -> None:
    recorder, source, plan = local_run
    if failure == "exit":
        plan[0]["argv"] = [sys.executable, "-I", "-c", "raise SystemExit(7)"]
        assert recorder.run(plan[0]["protocol"], plan[0]["argv"]).returncode == 7
    else:
        error = FileNotFoundError("missing executable") if failure == "launch" else KeyboardInterrupt()
        def fail(*args, **kwargs):
            raise error
        monkeypatch.setattr("scripts.local_verification.subprocess.run", fail)
        with pytest.raises(type(error)):
            recorder.run(plan[0]["protocol"], plan[0]["argv"])
    # A termination before finish leaves an explicit incomplete manifest.
    with pytest.raises(ValueError, match="incomplete"):
        check_bundle(recorder.path, plan, source, recorder.root, frozenset({"lockFileSha256", "pythonLockStatus"}))
    recorder.finish(1, source, failure)
    assert check_bundle(recorder.path, plan, source, recorder.root, frozenset({"lockFileSha256", "pythonLockStatus"}))["result"] == "failed"


@pytest.mark.parametrize("mutation", ["source", "locks", "partial"])
def test_unstable_or_partial_execution_cannot_finish_passed(local_run, mutation) -> None:
    recorder, source, plan = local_run
    final = copy.deepcopy(source)
    if mutation != "partial":
        recorder.run(plan[0]["protocol"], plan[0]["argv"])
    if mutation == "source":
        final["fingerprint"]["base_commit"] = "d" * 40
    if mutation == "locks":
        final["lockFileSha256"]["poetry.lock"] = "d" * 64
    recorder.finish(0, final)
    assert check_bundle(recorder.path, plan, source, recorder.root, frozenset({"lockFileSha256", "pythonLockStatus"}))["result"] == "failed"


@pytest.mark.parametrize("mutation", [
    "log-bytes", "missing-log", "path", "argv", "source", "lock-binding",
    "boolean-exit", "bad-time", "missing-tree", "unknown-field", "duplicate-key",
    "cwd", "time-order", "environment",
])
def test_offline_check_rejects_inconsistent_or_malformed_material(local_run, mutation) -> None:
    recorder, source, plan = local_run
    _pass(recorder, source, plan)
    if mutation == "log-bytes":
        (recorder.path / "00.log").write_bytes(b"tampered")
    elif mutation == "missing-log":
        (recorder.path / "00.log").unlink()
    elif mutation == "duplicate-key":
        manifest = recorder.path / "manifest.json"
        manifest.write_text('{"result":"passed",' + manifest.read_text()[1:], encoding="utf-8")
    else:
        def change(value):
            if mutation == "path":
                value["commands"][0]["log"] = "../elsewhere"
            elif mutation == "argv":
                value["plan"][0]["argv"] = ["echo", "not the verifier"]
                value["commands"][0]["argv"] = value["plan"][0]["argv"]
            elif mutation == "source":
                value["initial"]["tree"] = value["final"]["tree"] = "d" * 40
            elif mutation == "lock-binding":
                value["environment"]["lockFileSha256"]["Cargo.lock"] = "d" * 64
            elif mutation == "boolean-exit":
                value["commands"][0]["returnCode"] = False
            elif mutation == "bad-time":
                value["startedAt"] = "garbage"
            elif mutation == "missing-tree":
                del value["initial"]["tree"]
            elif mutation == "unknown-field":
                value["gateAccepted"] = True
            elif mutation == "cwd":
                value["cwd"] = "/somewhere/else"
            elif mutation == "time-order":
                value["commands"][0]["finishedAt"] = "2000-01-01T00:00:00+00:00"
            elif mutation == "environment":
                del value["environment"]["pythonLockStatus"]
        _edit(recorder, change)
    with pytest.raises((ValueError, OSError)):
        check_bundle(recorder.path, plan, source, recorder.root, frozenset({"lockFileSha256", "pythonLockStatus"}))


def test_nonregular_log_is_rejected_before_opening(local_run) -> None:
    recorder, source, plan = local_run
    _pass(recorder, source, plan)
    log = recorder.path / "00.log"
    log.unlink()
    if hasattr(os, "mkfifo"):
        os.mkfifo(log)
    else:
        log.mkdir()
    with pytest.raises(ValueError, match="regular file"):
        check_bundle(recorder.path, plan, source, recorder.root, frozenset({"lockFileSha256", "pythonLockStatus"}))


def test_recording_output_failure_keeps_incomplete_state(local_run, monkeypatch) -> None:
    recorder, source, plan = local_run
    def fail():
        raise OSError("disk full")
    monkeypatch.setattr(recorder, "_save", fail)
    with pytest.raises(OSError, match="disk full"):
        recorder.run(plan[0]["protocol"], plan[0]["argv"])
    with pytest.raises(ValueError):
        check_bundle(recorder.path, plan, source, recorder.root, frozenset({"lockFileSha256", "pythonLockStatus"}))


def test_capture_requires_ignored_directory(tmp_path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    with pytest.raises(ValueError, match="ignored"):
        LocalRunRecorder(tmp_path, {}, [])
