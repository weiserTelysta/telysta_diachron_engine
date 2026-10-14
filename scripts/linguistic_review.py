"""Run pinned, read-only linguistic review checks; never execute future adapters.

The JSON registry selects built-in test groups, not commands/plugins. Passing
these checks validates planning material, not a generated language or Gate.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any

from jsonschema import Draft202012Validator

if __package__:
    from .generate_gate_evidence import fingerprint_workspace
    from .pytest_runner import run_pytest
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from generate_gate_evidence import fingerprint_workspace
    from pytest_runner import run_pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "experiments/linguistic-execution/manifest.json"
SCHEMA = ROOT / "experiments/linguistic-execution/manifest.schema.json"
PACKS = {
    "regression": "tests/fixtures/linguistic_regression_cases_v1.json",
    "meaning": "tests/fixtures/meaning_review_vectors_v1.json",
    "orthography": "tests/fixtures/orthography_review_vectors_v1.json",
}
RUNNERS = {
    "regression-contracts": ("tests/core/test_audit_correction_fixture_contract.py",),
    "meaning-oracles": ("tests/core/test_meaning_review_vectors.py",),
    "concepticon-research": ("tests/core/test_concepticon_slice.py",),
    "orthography-relations": ("tests/core/test_orthography_review_vectors.py",),
}
REVIEW_SCOPES = {
    "regression-contracts": "Fixture contract checks, not production domain probes.",
    "meaning-oracles": "Four finite Meaning review vectors, not production analyzability.",
    "concepticon-research": "Twelve-entry research slice and membership, not full CLDF validation.",
    "orthography-relations": "Five declared finite relation facets only; no normalizer, parser, history execution or full 22-case validation.",
}
LOCK_PATHS = {
    *PACKS.values(), *(path for paths in RUNNERS.values() for path in paths),
    "experiments/concepticon-slice/lock.json", "experiments/concepticon-slice/slice.json",
    "scripts/concepticon_slice.py", "scripts/linguistic_review.py",
    "scripts/pytest_runner.py", "scripts/generate_gate_evidence.py", "poetry.lock",
    "pyproject.toml",
}


def _read_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate registry key")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _locked_path(relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or str(path) != relative or "\\" in relative:
        raise ValueError("lock path must be canonical repository-relative POSIX text")
    local = ROOT / relative
    if local.resolve() != local.absolute() or not local.is_file():
        raise ValueError("lock path is missing or traverses a link")
    return local


def _expected_bindings() -> dict[str, dict[str, dict[str, str]]]:
    bindings = {}
    for key, path in PACKS.items():
        pack = _read_json(ROOT / path)
        declared_status = (
            pack["fixtureProtocol"]["runnerStatus"] if key == "regression"
            else pack["runnerBinding"] if key == "meaning"
            else pack["productionRunnerStatus"]
        )
        if declared_status != ("future" if key == "orthography" else "future_not_bound"):
            raise ValueError("fixture runner status requires a new registry decision")
        cases = {}
        for case in pack["cases"]:
            if key == "regression":
                case_id = case["fixtureId"]
                contract, execution = case["contractGate"], case["executionGate"]
                adapter = case["runnerBinding"]["adapter"]
                if case["runnerBinding"]["status"] != "future":
                    raise ValueError("registry must be reviewed before binding real adapters")
            else:
                case_id = case["fixtureId"] if key == "meaning" else case["id"]
                contract, execution = "G0B", "G2"
                adapter = f"{key}_roundtrip_review_future.v1"
            if case_id in cases:
                raise ValueError("duplicate fixture case ID")
            cases[case_id] = {
                "contractGate": contract, "executionGate": execution,
                "adapterKey": adapter, "status": "future_not_bound",
            }
        if not cases:
            raise ValueError("fixture pack must not be empty")
        bindings[key] = cases
    return bindings


def validate_registry(manifest: dict[str, Any]) -> None:
    schema = _read_json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors:
        raise ValueError(errors[0].message)
    if manifest["schemaSha256"] != _sha(SCHEMA):
        raise ValueError("registry schema hash mismatch")
    if set(manifest["inputLocks"]) != LOCK_PATHS:
        raise ValueError("missing or unexpected input lock")
    for relative, expected in manifest["inputLocks"].items():
        if _sha(_locked_path(relative)) != expected:
            raise ValueError(f"stale input lock: {relative}")
    if set(manifest["reviewChecks"]) != set(RUNNERS):
        raise ValueError("missing or unknown built-in review runner")
    if manifest["productionBindings"] != _expected_bindings():
        raise ValueError("case-to-Gate/adapter mapping differs from fixture or future contract")


def run_review(manifest: dict[str, Any], *, execute: bool = False) -> dict[str, Any]:
    before = asdict(fingerprint_workspace(ROOT))
    validate_registry(manifest)
    results = []
    for key, paths in RUNNERS.items():
        if not execute:
            results.append({"runnerKey": key, "scope": REVIEW_SCOPES[key], "status": "not_executed"})
            continue
        result = run_pytest((*paths, "-q"), capture_output=True, require_all_passed=True)
        complete = (
            result.passed and type(result.collected) is int and result.collected > 0
            and result.executed == result.collected
            and result.passed_calls == result.collected
        )
        results.append({
            "runnerKey": key, "status": "pass" if complete else "fail",
            "scope": REVIEW_SCOPES[key],
            "collected": result.collected, "executed": result.executed,
            "passedCalls": result.passed_calls,
            "returncode": result.returncode, "pytestReturncode": result.pytest_returncode,
            "failureReason": (
                result.failure_reason if complete or result.failure_reason
                else "not all selected tests passed"
            ),
            "stdout": result.stdout, "stderr": result.stderr,
        })
    after = asdict(fingerprint_workspace(ROOT))
    # Recheck locked bytes as well as the whole source identity after running.
    # Neither this nor the local report is a trusted remote attestation.
    validate_registry(manifest)
    status = "source_changed" if before != after else (
        "review_checks_failed" if any(item["status"] == "fail" for item in results)
        else "review_checks_passed" if execute else "manifest_validated_no_checks_executed"
    )
    return {
        "schemaVersion": "telysta-linguistic-review-report-draft.v1",
        "status": status, "timestampUtc": datetime.now(timezone.utc).isoformat(),
        "manifestSha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "manifestHashEncoding": "parsed-json-sorted-keys-ascii-compact.v1",
        "sourceBefore": before, "sourceAfter": after,
        "pythonVersion": sys.version, "pythonExecutable": sys.executable,
        "reviewChecks": results, "productionBindings": manifest["productionBindings"],
        "productionCasesExecuted": 0, "capabilityClaims": [], "gateDecision": "not_evaluated",
        "limitations": [
            "Checks concern fixture contracts and research data, not production linguistic behavior.",
            "Future bindings are symbolic adapter keys, not accepted adapter schemas or implementations.",
            "No sealed audit, human approval or trusted cross-platform attestation is supplied.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Execute all built-in review test groups")
    args = parser.parse_args()
    try:
        report = run_review(_read_json(MANIFEST), execute=args.run)
    except (OSError, ValueError) as error:
        report = {
            "schemaVersion": "telysta-linguistic-review-report-draft.v1",
            "status": "invalid_registry", "error": str(error),
            "productionCasesExecuted": 0, "capabilityClaims": [],
            "gateDecision": "not_evaluated",
        }
        print(json.dumps(report, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] in {"review_checks_passed", "manifest_validated_no_checks_executed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
