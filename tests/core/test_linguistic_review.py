"""Check that research execution never promotes future linguistic capability."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import linguistic_review as review
from scripts.generate_gate_evidence import WorkspaceFingerprint


def _manifest() -> dict:
    return review._read_json(review.MANIFEST)


def _stable_source(monkeypatch: pytest.MonkeyPatch) -> WorkspaceFingerprint:
    source = WorkspaceFingerprint(base_commit="a" * 40, dirty=False, status_entry_count=0, sha256="b" * 64)
    monkeypatch.setattr(review, "fingerprint_workspace", lambda root: source)
    return source


def test_review_registry_covers_every_case_and_preserves_distinct_execution_gates() -> None:
    manifest = _manifest()
    review.validate_registry(manifest)
    bindings = manifest["productionBindings"]
    assert {key: len(value) for key, value in bindings.items()} == {"regression": 24, "meaning": 4, "orthography": 22}
    assert bindings["regression"]["DATA-N01"]["executionGate"] == "G0B"
    assert bindings["regression"]["GRA-N01"]["executionGate"] == "G4"
    assert bindings["regression"]["ANA-N01"]["executionGate"] == "G4"
    assert all(item["status"] == "future_not_bound" for pack in bindings.values() for item in pack.values())


def test_review_registry_rejects_capability_promotion_missing_cases_and_command_injection() -> None:
    mutants = []
    for change in ("status", "gate", "adapter", "missing", "extra"):
        item = _manifest()
        bindings = item["productionBindings"]["regression"]
        if change == "status":
            bindings["PH-N01"]["status"] = "pass"
        elif change == "gate":
            bindings["DATA-N01"]["executionGate"] = "G2"
        elif change == "adapter":
            bindings["PH-N01"]["adapterKey"] = "pretend_compiler.v1"
        elif change == "missing":
            del bindings["PH-N01"]
        else:
            bindings["NEW-ID"] = copy.deepcopy(bindings["PH-N01"])
        mutants.append(item)
    for change in ("command", "count", "runner", "claim"):
        item = _manifest()
        if change == "command":
            item["reviewChecks"]["meaning-oracles"]["argv"] = ["sh", "-c", "exit 0"]
        elif change == "count":
            item["reviewChecks"]["meaning-oracles"]["productionCasesExecuted"] = 1
        elif change == "runner":
            del item["reviewChecks"]["meaning-oracles"]
        else:
            item["capabilityClaims"] = ["G-LANG passed"]
        mutants.append(item)
    for mutant in mutants:
        with pytest.raises(ValueError):
            review.validate_registry(mutant)


def test_review_registry_rejects_missing_stale_and_unexpected_hash_locks() -> None:
    for change in ("stale", "missing", "extra", "schema"):
        item = _manifest()
        if change == "stale":
            item["inputLocks"]["scripts/concepticon_slice.py"] = "0" * 64
        elif change == "missing":
            item["inputLocks"].pop("poetry.lock")
        elif change == "extra":
            item["inputLocks"]["references/private.pdf"] = "0" * 64
        else:
            item["schemaSha256"] = "0" * 64
        with pytest.raises(ValueError):
            review.validate_registry(item)


def test_review_preview_runs_no_tests_and_claims_no_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    _stable_source(monkeypatch)
    monkeypatch.setattr(review, "run_pytest", lambda *args, **kwargs: pytest.fail("preview must not execute"))
    result = review.run_review(_manifest())
    assert result["status"] == "manifest_validated_no_checks_executed"
    assert all(item["status"] == "not_executed" for item in result["reviewChecks"])
    assert result["productionCasesExecuted"] == 0
    assert result["capabilityClaims"] == [] and result["gateDecision"] == "not_evaluated"


@pytest.mark.parametrize("counts,passed", [((0, 0), True), ((5, 0), True), ((5, 4), True), ((5, 5), False)])
def test_review_zero_partial_and_failed_execution_cannot_pass(
    monkeypatch: pytest.MonkeyPatch, counts: tuple[int, int], passed: bool,
) -> None:
    _stable_source(monkeypatch)
    collected, executed = counts
    calls = []
    def run(arguments: tuple, **kwargs: dict) -> SimpleNamespace:
        calls.append((arguments, kwargs))
        return SimpleNamespace(
            passed=passed, collected=collected, executed=executed,
            returncode=0 if passed else 1, pytest_returncode=0 if passed else 1,
            failure_reason=None if passed else "failed", stdout="raw test output", stderr="",
        )
    monkeypatch.setattr(review, "run_pytest", run)
    result = review.run_review(_manifest(), execute=True)
    assert result["status"] == "review_checks_failed"
    assert len(calls) == 3
    assert [args for args, _ in calls] == [(*paths, "-q") for paths in review.RUNNERS.values()]
    assert all(kwargs == {"capture_output": True} for _, kwargs in calls)
    assert result["productionCasesExecuted"] == 0 and result["gateDecision"] == "not_evaluated"


def test_review_detects_whole_source_change_even_without_input_lock_change(monkeypatch: pytest.MonkeyPatch) -> None:
    before = WorkspaceFingerprint(base_commit="a" * 40, dirty=False, status_entry_count=0, sha256="b" * 64)
    after = WorkspaceFingerprint(base_commit="a" * 40, dirty=True, status_entry_count=1, sha256="c" * 64)
    snapshots = iter([before, after])
    monkeypatch.setattr(review, "fingerprint_workspace", lambda root: next(snapshots))
    result = review.run_review(_manifest())
    assert result["status"] == "source_changed"
    assert result["sourceBefore"] != result["sourceAfter"]
    assert result["capabilityClaims"] == []


def test_review_lock_paths_reject_traversal_and_linked_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(review, "ROOT", tmp_path)
    (tmp_path / "plain.json").write_text("{}")
    assert review._locked_path("plain.json") == tmp_path / "plain.json"
    for relative in ("../plain.json", "/tmp/file", "a/../plain.json", "./plain.json", "a\\plain.json", "missing.json"):
        with pytest.raises(ValueError):
            review._locked_path(relative)
    # Model an input resolving elsewhere without requiring Windows symlink
    # privileges. Actual Linux links are additionally checked in review.
    resolve = Path.resolve
    def linked_resolve(path: Path, *args: object, **kwargs: object) -> Path:
        if path == tmp_path / "linked.json":
            return tmp_path / "plain.json"
        return resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", linked_resolve)
    with pytest.raises(ValueError, match="link"):
        review._locked_path("linked.json")


def test_review_json_reader_rejects_duplicate_bindings(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"x":{"a":null,"\\u0061":null}}')
    with pytest.raises(ValueError, match="duplicate"):
        review._read_json(path)


def test_review_actual_fixed_groups_execute_without_promoting_future_bindings() -> None:
    result = review.run_review(_manifest(), execute=True)
    assert result["status"] == "review_checks_passed"
    assert [item["executed"] for item in result["reviewChecks"]] == [9, 8, 15]
    assert all(item["returncode"] == 0 and item["collected"] == item["executed"] for item in result["reviewChecks"])
    assert result["productionCasesExecuted"] == 0 and result["gateDecision"] == "not_evaluated"
    assert all(item["status"] == "future_not_bound" for pack in result["productionBindings"].values() for item in pack.values())
    assert result["capabilityClaims"] == []
