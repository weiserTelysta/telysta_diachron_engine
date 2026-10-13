"""Executable review checks for the planning-only ADR-011 contract fixtures.

These checks deliberately do not implement a project writer or teach the
Python engine a new persistence schema. They make the proposed identity and
sequence decisions reviewable before any Rust production implementation is
allowed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import pytest
from scripts.generate_gate_evidence import fingerprint_workspace, render_status


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs" / "ADR_011_SCHEMA_DRAFT_V1.json"
SCHEMA_RECORDS_PATH = ROOT / "tests" / "fixtures" / "adr_011_schema_records_v1.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "adr_011_sequences_v1.json"
G0A_EVIDENCE_PATH = ROOT / "docs" / "G0A_GATE_EVIDENCE_2026-07-17.json"

SHA256 = re.compile(r"^[0-9a-f]{64}$")
TYPED_ID = re.compile(
    r"^telysta:(project|operation|run|job|attempt|event):"
    r"[a-z0-9](?:[a-z0-9-]{0,94}[a-z0-9])?$"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _assert_id(value: str, kind: str) -> None:
    match = TYPED_ID.fullmatch(value)
    assert match is not None, value
    assert match.group(1) == kind, value


def _schema_validator() -> Draft202012Validator:
    schema = _load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _assert_run_and_checkpoint_locks(records: dict[str, Any]) -> None:
    operations = {item["operationId"]: item for item in records["operationSpecs"]}
    runs = {item["runId"]: item for item in records["runSpecs"]}
    jobs = {item["jobId"]: item for item in records["jobRecords"]}
    attempts = {item["attemptId"]: item for item in records["attemptRecords"]}
    for index, collection in ((operations, "operationSpecs"), (runs, "runSpecs"),
                              (jobs, "jobRecords"), (attempts, "attemptRecords")):
        assert len(index) == len(records[collection])
    for operation in operations.values():
        lock = operation["rngLock"]
        if lock["kind"] == "rng_tree":
            paths = [item["relativePath"] for item in lock["streamBudgets"]]
            assert len(paths) == len(set(paths))
    keys = set()
    for run in runs.values():
        operation = operations[run["operationId"]]
        assert run["operationSpecSha256"] == operation["operationSpecSha256"]
        assert run["parameterSha256"] == operation["parameterSha256"]
        key = (run["operationId"], run["role"], run["runKey"])
        assert key not in keys
        keys.add(key)
        parent_lock, run_lock = operation["rngLock"], run["rngLock"]
        assert parent_lock["kind"] == run_lock["kind"]
        if parent_lock["kind"] == "no_rng":
            continue
        assert {k: v for k, v in parent_lock.items() if k != "pathRoot"} == {
            k: v for k, v in run_lock.items() if k != "pathRoot"
        }
        assert run_lock["pathRoot"] == f"{parent_lock['pathRoot']}.{run['role']}.{run['runKey']}"
        paths = [item["relativePath"] for item in run_lock["streamBudgets"]]
        assert len(paths) == len(set(paths))
    for checkpoint in records["checkpointRecords"]:
        attempt = attempts[checkpoint["attemptId"]]
        run = runs[jobs[attempt["jobId"]]["runId"]]
        operation = operations[run["operationId"]]
        assert checkpoint["operationSpecSha256"] == run["operationSpecSha256"]
        assert checkpoint["runSpecSha256"] == run["runSpecSha256"]
        assert checkpoint["baseHistorySha256"] == operation["expectedHistorySha256"]
        frontier = checkpoint["rngFrontier"]
        raw = json.dumps(frontier, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        assert checkpoint["rngFrontierSha256"] == hashlib.sha256(raw).hexdigest()
        lock = run["rngLock"]
        budgets = {} if lock["kind"] == "no_rng" else {
            f"{lock['pathRoot']}.{item['relativePath']}": item["maxRawDraws"] for item in lock["streamBudgets"]
        }
        streams = frontier["streams"]
        assert len(streams) == len(budgets) and {item["path"] for item in streams} == set(budgets)
        for stream in streams:
            assert stream["distributionVersion"] == lock["distributionVersion"]
            assert stream["maxRawDraws"] == budgets[stream["path"]]
            assert 0 <= stream["nextCounter"] == stream["consumedRawDraws"] <= stream["maxRawDraws"]


def _refresh_frontier_hash(checkpoint: dict[str, Any]) -> None:
    raw = json.dumps(checkpoint["rngFrontier"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    checkpoint["rngFrontierSha256"] = hashlib.sha256(raw).hexdigest()


def test_planning_seed_wire_is_canonical_decimal_and_matches_integer_range_oracle() -> None:
    definitions = _load(SCHEMA_PATH)["$defs"]
    validator = Draft202012Validator({"$ref": "#/$defs/u64Decimal", "$defs": definitions})
    maximum = 2**64 - 1
    values = set(range(1024)) | set(range(maximum - 1024, maximum + 1025))
    values |= {10**power + offset for power in range(1, 21) for offset in (-1, 0, 1)}
    values |= {2**53 - 1, 2**53, 2**53 + 1}
    bound = str(maximum)
    for index in range(len(bound)):
        for digit in "0123456789":
            for fill in "09":
                values.add(int(bound[:index] + digit + fill * (len(bound) - index - 1)))
    for value in values:
        assert validator.is_valid(str(value)) == (0 <= value <= maximum), value
    for invalid in ("", "00", "01", "-0", "-1", "+1", "1.0", "1e3", " 1", "1 ", "0\n", "١", "１", 0, maximum, None):
        assert not validator.is_valid(invalid), invalid


def test_run_variants_inherit_inputs_and_only_derive_their_stream_root() -> None:
    records = _load(SCHEMA_RECORDS_PATH)
    second = copy.deepcopy(records["runSpecs"][0])
    second.update(runId="telysta:run:genesis-candidate-0002", runKey="0002", runSpecSha256="d" * 64)
    second["rngLock"]["pathRoot"] = "genesis.phonology_core.candidate.0002"
    records["runSpecs"].append(second)
    _schema_validator().validate(records)
    _assert_run_and_checkpoint_locks(records)
    for mutation in ("seed", "parameters", "root", "distribution", "budget", "duplicate_key"):
        mutant = copy.deepcopy(records)
        run = mutant["runSpecs"][1]
        if mutation == "seed":
            run["rngLock"]["rootSeed"] = "889"
        elif mutation == "parameters":
            run["parameterSha256"] = "0" * 64
        elif mutation == "root":
            run["rngLock"]["pathRoot"] = "unrelated.stream"
        elif mutation == "distribution":
            run["rngLock"]["distributionVersion"] = "unknown.v9"
        elif mutation == "budget":
            run["rngLock"]["streamBudgets"][0]["maxRawDraws"] += 1
        else:
            run["runKey"] = "0001"
            run["rngLock"]["pathRoot"] = "genesis.phonology_core.candidate.0001"
        with pytest.raises(AssertionError):
            _assert_run_and_checkpoint_locks(mutant)


def test_operation_budget_is_unambiguous_before_any_run_is_registered() -> None:
    records = _load(SCHEMA_RECORDS_PATH)
    operation = copy.deepcopy(records["operationSpecs"][0])
    operation.update(operationId="telysta:operation:unstarted", idempotencyKey="unstarted-request")
    records["operationSpecs"].append(operation)
    _schema_validator().validate(records)
    _assert_run_and_checkpoint_locks(records)
    operation["rngLock"]["streamBudgets"].append({"relativePath": "draws", "maxRawDraws": 2048})
    _schema_validator().validate(records)
    with pytest.raises(AssertionError):
        _assert_run_and_checkpoint_locks(records)


def test_rng_frontier_rejects_missing_or_rehashed_inconsistent_recovery_locks() -> None:
    baseline = _load(SCHEMA_RECORDS_PATH)
    validator = _schema_validator()
    missing = copy.deepcopy(baseline)
    del missing["runSpecs"][0]["rngLock"]["streamBudgets"]
    assert list(validator.iter_errors(missing))
    oversized = copy.deepcopy(baseline)
    oversized["runSpecs"][0]["rngLock"]["streamBudgets"][0]["maxRawDraws"] = 2**53
    assert list(validator.iter_errors(oversized))
    for mutation in ("budget", "path", "counter", "over_budget", "duplicate", "hash"):
        mutant = copy.deepcopy(baseline)
        checkpoint = mutant["checkpointRecords"][0]
        stream = checkpoint["rngFrontier"]["streams"][0]
        if mutation == "budget":
            stream["maxRawDraws"] += 1
        elif mutation == "path":
            stream["path"] = "undeclared.stream"
        elif mutation == "counter":
            stream["nextCounter"] += 1
        elif mutation == "over_budget":
            stream["nextCounter"] = stream["consumedRawDraws"] = 1025
        elif mutation == "duplicate":
            checkpoint["rngFrontier"]["streams"].append(dict(stream))
        _refresh_frontier_hash(checkpoint)
        if mutation == "hash":
            checkpoint["rngFrontierSha256"] = "0" * 64
        validator.validate(mutant)
        with pytest.raises(AssertionError):
            _assert_run_and_checkpoint_locks(mutant)
    exhausted = copy.deepcopy(baseline)
    checkpoint = exhausted["checkpointRecords"][0]
    stream = checkpoint["rngFrontier"]["streams"][0]
    stream["nextCounter"] = stream["consumedRawDraws"] = stream["maxRawDraws"]
    _refresh_frontier_hash(checkpoint)
    validator.validate(exhausted)
    _assert_run_and_checkpoint_locks(exhausted)
    assert not stream["consumedRawDraws"] < stream["maxRawDraws"]


def test_schema_draft_names_every_identity_and_recovery_record() -> None:
    schema = _load(SCHEMA_PATH)
    validator = _schema_validator()
    records = _load(SCHEMA_RECORDS_PATH)
    validator.validate(records)
    _assert_run_and_checkpoint_locks(records)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "Planning-only" in schema["description"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["x-telysta-status"] == "planning_only_not_a_production_persistence_format"
    assert schema["x-telysta-projectAuthorityHashOwner"] == "ADR-012"
    assert schema["x-telysta-projectAuthorityHashFixtureStatus"] == (
        "format_sentinel_only_missing_canonicalizer_coverage_and_known_answer"
    )
    assert schema["x-telysta-entityIdSchema"] == "telysta-entity-id.v1"
    assert set(schema["x-telysta-proposedEntityKinds"]) == {"operation", "job", "attempt"}

    definitions = schema["$defs"]
    required_definitions = {
        "projectManifest",
        "operationSpec",
        "runSpec",
        "runLedgerEntry",
        "jobRecord",
        "attemptRecord",
        "checkpointRecord",
    }
    assert required_definitions <= definitions.keys()

    assert {
        "projectId",
        "historyHeads",
        "eventStoreRootSha256",
        "runLedgerHeadSha256",
        "usageCorpusRootSha256",
        "migrationMetadata",
        "projectAuthorityHash",
    } <= set(definitions["projectManifest"]["required"])
    authority_hash = definitions["projectManifest"]["properties"][
        "projectAuthorityHash"
    ]
    assert authority_hash["$ref"] == "#/$defs/sha256"
    assert "excluding this field itself" in authority_hash["description"]
    assert {
        "operationId",
        "projectId",
        "expectedHistorySha256",
        "rngLock",
        "idempotencyKey",
        "operationSpecSha256",
    } <= set(definitions["operationSpec"]["required"])
    assert {
        "runId",
        "operationId",
        "operationSpecSha256",
        "rngLock",
        "runSpecSha256",
    } <= set(definitions["runSpec"]["required"])
    assert {"jobId", "runId", "state", "attemptIds"} <= set(
        definitions["jobRecord"]["required"]
    )
    assert {"attemptId", "jobId", "kind", "state"} <= set(
        definitions["attemptRecord"]["required"]
    )
    assert {
        "operationSpecSha256",
        "runSpecSha256",
        "baseHistorySha256",
        "dependencyBundleSha256",
        "rngFrontierSha256",
        "checkpointSha256",
    } <= set(definitions["checkpointRecord"]["required"])


def test_schema_draft_rejects_identity_rng_migration_and_unknown_field_drift() -> None:
    validator = _schema_validator()
    records = _load(SCHEMA_RECORDS_PATH)
    invalid_records: list[dict[str, Any]] = []

    underscore_id = copy.deepcopy(records)
    underscore_id["operationSpecs"][0]["operationId"] = "telysta:operation:invalid_value"
    invalid_records.append(underscore_id)

    oversized_id = copy.deepcopy(records)
    oversized_id["jobRecords"][0]["jobId"] = f"telysta:job:{'a' * 97}"
    invalid_records.append(oversized_id)

    seed_overflow = copy.deepcopy(records)
    seed_overflow["runSpecs"][0]["rngLock"]["rootSeed"] = str(2**64)
    invalid_records.append(seed_overflow)

    invalid_rng_path = copy.deepcopy(records)
    invalid_rng_path["runSpecs"][0]["rngLock"]["pathRoot"] = "genesis..phonology"
    invalid_records.append(invalid_rng_path)

    incomplete_legacy_metadata = copy.deepcopy(records)
    incomplete_legacy_metadata["projectManifests"][0]["migrationMetadata"]["kind"] = "legacy_import"
    invalid_records.append(incomplete_legacy_metadata)

    unknown_authoritative_field = copy.deepcopy(records)
    unknown_authoritative_field["projectManifests"][0]["uiState"] = {"selectedTab": "history"}
    invalid_records.append(unknown_authoritative_field)

    for invalid in invalid_records:
        assert list(validator.iter_errors(invalid)), invalid


def test_sequence_fixtures_keep_semantic_and_execution_identity_separate() -> None:
    fixture = _load(FIXTURE_PATH)
    assert fixture["schemaVersion"] == "telysta-adr-011-sequence-fixtures.v1"
    assert fixture["contractSchema"] == "docs/ADR_011_SCHEMA_DRAFT_V1.json"
    assert fixture["status"] == "planning_only_not_a_production_persistence_format"

    cases = {case["caseId"]: case for case in fixture["cases"]}
    assert set(cases) == {
        "genesis_create",
        "authoring_without_background_run",
        "simulation_multiple_runs_one_commit",
        "legacy_v1_import_boundary",
    }

    for case in cases.values():
        _assert_id(case["projectId"], "project")
        operation = case["operation"]
        _assert_id(operation["operationId"], "operation")
        assert SHA256.fullmatch(operation["requestSha256"])
        assert operation["idempotencyKey"].strip()

        run_ids: set[str] = set()
        run_by_id = {run["runId"]: run for run in case["runs"]}
        for run in case["runs"]:
            _assert_id(run["runId"], "run")
            assert run["operationId"] == operation["operationId"]
            assert SHA256.fullmatch(run["resultSha256"])
            assert run["runId"] not in run_ids
            run_ids.add(run["runId"])

        job_ids: set[str] = set()
        attempt_ids: set[str] = set()
        for job in case["jobs"]:
            _assert_id(job["jobId"], "job")
            assert job["runId"] in run_ids
            assert job["jobId"] not in job_ids
            job_ids.add(job["jobId"])
            for attempt in job["attempts"]:
                _assert_id(attempt["attemptId"], "attempt")
                assert attempt["jobId"] == job["jobId"]
                assert attempt["attemptId"] not in attempt_ids
                attempt_ids.add(attempt["attemptId"])
                if attempt["state"] == "completed":
                    assert SHA256.fullmatch(attempt["resultSha256"])
                    assert attempt["resultSha256"] == run_by_id[job["runId"]]["resultSha256"]

        ledger = case["ledger"]
        assert [entry["sequence"] for entry in ledger] == list(range(1, len(ledger) + 1))
        assert ledger[0]["kind"] == "operation_declared"
        assert all(entry["operationId"] == operation["operationId"] for entry in ledger)
        assert all(entry["runId"] is None or entry["runId"] in run_ids for entry in ledger)

        semantic_refs = set(case["semanticIdentityRefs"])
        forbidden_refs = set(case["forbiddenSemanticRefs"])
        assert semantic_refs.isdisjoint(forbidden_refs)
        assert not any(ref.startswith(("telysta:job:", "telysta:attempt:")) for ref in semantic_refs)
        assert forbidden_refs == job_ids | attempt_ids

    genesis = cases["genesis_create"]
    assert genesis["baseHistorySha256"] is None
    assert genesis["ledger"][-1]["kind"] == "operation_committed"

    authoring = cases["authoring_without_background_run"]
    assert authoring["runs"] == []
    assert authoring["jobs"] == []
    assert authoring["operation"]["disposition"] == "committed"

    simulation = cases["simulation_multiple_runs_one_commit"]
    simulation_run_ids = {run["runId"] for run in simulation["runs"]}
    assert len(simulation_run_ids) >= 2
    assert simulation["operation"]["selectedRunId"] in simulation_run_ids
    assert simulation["ledger"][-1]["runId"] == simulation["operation"]["selectedRunId"]

    legacy = cases["legacy_v1_import_boundary"]
    boundary = legacy["legacyBoundary"]
    assert boundary["sourceSchema"] == "telysta-project-history.v1"
    assert SHA256.fullmatch(boundary["sourceArtifactSha256"])
    assert boundary["archiveRequired"] is True
    assert boundary["noInferredOperations"] is True
    _assert_id(boundary["boundaryEventId"], "event")


def test_negative_cases_cover_every_adr_011_stop_condition() -> None:
    fixture = _load(FIXTURE_PATH)
    negative = {case["kind"]: case for case in fixture["negativeCases"]}
    assert set(negative) == {
        "idempotency_conflict",
        "stale_commit",
        "resume_missing_lock",
        "determinism_failure",
        "commit_crash",
    }
    assert negative["idempotency_conflict"]["expectedDecision"] == "reject"
    assert negative["stale_commit"]["expectedDecision"] == "retain_staging_without_commit"
    assert negative["resume_missing_lock"]["expectedDecision"] == "restart_only"
    assert negative["determinism_failure"]["expectedDecision"] == "reject_all_results"
    assert negative["commit_crash"]["expectedDecision"] == "recover_pre_or_post_commit_only"
    assert all(case["expectedCode"].strip() for case in negative.values())


def _assert_publication_review(review: dict[str, Any]) -> None:
    assert review["runnerStatus"] == "future_not_bound"
    graphs = review["graphs"]
    recovery = review["recoveryRecord"]
    assert recovery["preManifestRef"] == graphs["pre"]["manifestRef"]
    assert recovery["postManifestRef"] == graphs["post"]["manifestRef"]
    assert set(recovery["protectGraphs"]) == {"pre", "post"}
    assert graphs["pre"]["roots"] != graphs["post"]["roots"]
    for graph in graphs.values():
        assert len(graph["roots"]) == len(set(graph["roots"])) == 3
        assert any("history-" in root for root in graph["roots"])
        assert any("ledger-" in root for root in graph["roots"])
        assert "fixture:object:dependencies" in graph["roots"]
    faults = {item["phase"]: item for item in review["faults"]}
    expected = {
        "object_sync_failed": ("not_published", False),
        "candidate_sync_failed": ("not_published", False),
        "recovery_record_sync_failed": ("not_published", True),
        "before_replace": ("not_published", True),
        "replace_result_uncertain": ("commit_outcome_unknown", True),
        "directory_sync_failed_after_replace": ("commit_outcome_unknown", True),
        "post_publish_validation_failed": ("commit_outcome_unknown", True),
        "job_update_failed": ("committed_job_reconciliation_pending", False),
    }
    assert len(faults) == len(review["faults"]) == len(expected)
    assert set(faults) == set(expected)
    for fault in faults.values():
        assert (fault["return"], fault["recoveryPending"]) == expected[fault["phase"]]
        if fault["visible"] in graphs:
            assert fault["allowedAuthority"] == [fault["visible"]]
        else:
            assert fault["visible"] == "unknown"
            assert set(fault["allowedAuthority"]) == {"pre", "post"}
        if fault["return"] == "not_published":
            assert fault["visible"] == "pre"
        if fault["return"] == "commit_outcome_unknown":
            assert fault["recoveryPending"] is True
    assert faults["directory_sync_failed_after_replace"]["return"] == "commit_outcome_unknown"
    assert faults["post_publish_validation_failed"]["return"] == "commit_outcome_unknown"
    assert faults["job_update_failed"]["return"] == "committed_job_reconciliation_pending"


def test_publication_planning_faults_preserve_both_graphs_until_outcome_is_resolved() -> None:
    _assert_publication_review(_load(FIXTURE_PATH)["publicationReview"])


def test_uncertain_replace_cannot_be_declared_committed_or_discard_recovery() -> None:
    review = _load(FIXTURE_PATH)["publicationReview"]
    for mutation in ("committed", "discard_recovery"):
        mutant = copy.deepcopy(review)
        fault = next(item for item in mutant["faults"] if item["phase"] == "replace_result_uncertain")
        if mutation == "committed":
            fault["return"] = "committed"
        else:
            fault["recoveryPending"] = False
        with pytest.raises(AssertionError):
            _assert_publication_review(mutant)


def test_g0a_evidence_cannot_misreport_an_unreviewed_gate_as_passed() -> None:
    evidence = _load(G0A_EVIDENCE_PATH)
    fingerprint = fingerprint_workspace(ROOT)
    source = evidence["source"]
    subject = source["subjectCommit"]

    assert evidence["schemaVersion"] == "telysta-gate-evidence-manifest.v3"
    assert evidence["gateId"] == "G0A"
    assert evidence["decision"] == "blocked"
    assert source["subjectTree"] == _git(
        "rev-parse", f"{subject}^{{tree}}"
    ).decode("ascii").strip()
    assert (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", subject, fingerprint.base_commit],
            cwd=ROOT,
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )
    if (
        subject == fingerprint.base_commit
        and source["worktreeInventorySha256"] == fingerprint.sha256
    ):
        assert source["worktreeDirty"] is fingerprint.dirty
        assert source["worktreeStatusEntryCount"] == fingerprint.status_entry_count
    assert evidence["owner"] is None
    assert evidence["reviewers"] == []
    assert evidence["waivers"] == []

    requirement_status = {
        requirement["id"]: requirement["status"] for requirement in evidence["requirements"]
    }
    assert requirement_status["R0A-02-ADR011"] == "blocked"
    assert requirement_status["R0A-03"] == "ready_for_independent_review"
    assert requirement_status["R0A-04"] == "ready_for_independent_review"
    expected_clean_subject_status = (
        "failed" if source["worktreeDirty"] else "ready_for_independent_review"
    )
    assert requirement_status["R0A-05"] == expected_clean_subject_status
    assert requirement_status["R0A-07"] == "incomplete"
    assert requirement_status["R0A-08"] == "incomplete"
    assert requirement_status["R0A-09"] == "incomplete"
    assert requirement_status["R0A-10"] == "incomplete"
    assert evidence["deliveryReadiness"]["workPackages"] == []
    assert evidence["gatePolicy"]["schemaVersion"] == "telysta-g0a-policy.v2"

    forbidden_claims = set(evidence["claims"]["forbidden"])
    assert "G0A has passed" in forbidden_claims
    assert "ADR-011 is Accepted" in forbidden_claims
    assert "ADR-012 or ADR-013 is Accepted" in forbidden_claims
    assert "R1 persistent Project/Operation/Run/Job implementation may start" in forbidden_claims
    assert (ROOT / "docs" / "STATUS.md").read_text(encoding="utf-8") == render_status(
        evidence
    )


def test_g0a_evidence_content_hashes_match_the_recorded_subject() -> None:
    evidence = _load(G0A_EVIDENCE_PATH)
    fingerprint = fingerprint_workspace(ROOT)
    source = evidence["source"]
    evidence_is_fresh = (
        source["subjectCommit"] == fingerprint.base_commit
        and source["worktreeInventorySha256"] == fingerprint.sha256
    )
    hashed_items = [item for item in evidence["evidence"] if "sha256" in item]
    assert hashed_items

    for item in hashed_items:
        path = ROOT / item["path"]
        assert path.is_file(), item["path"]
        payload = (
            path.read_bytes()
            if evidence_is_fresh
            else _git("show", f"{source['subjectCommit']}:{item['path']}")
        )
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == item["sha256"], item["path"]
