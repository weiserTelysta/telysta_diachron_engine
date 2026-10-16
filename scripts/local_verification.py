"""Local diagnostic bundles, not Gate approvals or execution attestations.

Only the existing verifier supplies commands. This module saves their combined
raw output directly to disk and checks bundle consistency without running them.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from typing import Any

from jsonschema import Draft202012Validator


SCHEMA = "telysta-local-verification-bundle.v1"
SCOPE = "local-software-diagnostics-only"


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


_SHA = {"type": "string", "minLength": 64, "maxLength": 64, "pattern": "^[0-9a-f]{64}$"}
_COMMIT = {"type": "string", "minLength": 40, "maxLength": 40, "pattern": "^[0-9a-f]{40}$"}
_TEXT = {"type": "string", "minLength": 1}
_TIME = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T"}
_LOCKS = _object({"Cargo.lock": _SHA, "poetry.lock": _SHA})
_SOURCE = _object({
    "tree": _COMMIT, "lockFileSha256": _LOCKS,
    "fingerprint": _object({
        "base_commit": _COMMIT, "dirty": {"type": "boolean"},
        "status_entry_count": {"type": "integer", "minimum": 0}, "sha256": _SHA,
    }),
})
_ARGV = {"type": "array", "minItems": 1, "items": _TEXT}
_COMMAND = {"protocol": _TEXT, "argv": _ARGV}
_BUNDLE_SCHEMA = _object({
    "schemaVersion": {"const": SCHEMA}, "scope": {"const": SCOPE},
    "runId": _TEXT, "cwd": _TEXT, "startedAt": _TIME,
    "finishedAt": {"anyOf": [_TIME, {"type": "null"}]},
    "result": {"enum": ["incomplete", "failed", "passed"]},
    "initial": _SOURCE, "final": {"anyOf": [_SOURCE, {"type": "null"}]},
    "environment": {"anyOf": [{"type": "object", "required": ["lockFileSha256"],
                               "properties": {"lockFileSha256": _LOCKS,
                                              "pythonInstalledDistributionsSha256": _SHA}},
                              {"type": "null"}]},
    "plan": {"type": "array", "minItems": 1, "items": _object(_COMMAND)},
    "commands": {"type": "array", "items": _object({
        **_COMMAND, "startedAt": _TIME,
        "finishedAt": {"anyOf": [_TIME, {"type": "null"}]},
        "returnCode": {"type": ["integer", "null"]}, "error": {"type": ["string", "null"]},
        "log": _TEXT, "bytes": {"type": ["integer", "null"], "minimum": 0},
        "sha256": {"anyOf": [_SHA, {"type": "null"}]},
    })},
    "error": {"type": ["string", "null"]},
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(path: Path) -> dict[str, Any]:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("local log must be a regular file")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
            size += len(block)
    return {"bytes": size, "sha256": digest.hexdigest()}


class LocalRunRecorder:
    """An exclusive, ignored sidecar held inside the repository verifier lease."""

    def __init__(self, root: Path, initial: dict[str, Any], plan: list[dict[str, Any]]):
        parent = root / "target/local-verification"
        if parent.resolve() != parent.absolute():
            raise ValueError("local bundle directory must not traverse links")
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "target/local-verification/probe"],
            cwd=root, check=False,
        )
        if ignored.returncode != 0:
            raise ValueError("local bundle directory must be ignored by Git")
        parent.mkdir(parents=True, exist_ok=True)
        self.path = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
        self.root = root
        self.document = {
            "schemaVersion": SCHEMA, "scope": SCOPE,
            "runId": self.path.name, "cwd": str(root.resolve()),
            "startedAt": _now(), "finishedAt": None,
            "result": "incomplete", "initial": initial, "final": None,
            "environment": None, "plan": plan, "commands": [], "error": None,
        }
        self._save()

    def _save(self) -> None:
        descriptor, name = tempfile.mkstemp(prefix=".manifest-", dir=self.path)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(self.document, stream, ensure_ascii=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path / "manifest.json")
        finally:
            Path(name).unlink(missing_ok=True)

    def environment(self, value: dict[str, Any]) -> None:
        self.document["environment"] = value
        self._save()

    def run(self, protocol: str, argv: list[str]) -> subprocess.CompletedProcess:
        index = len(self.document["commands"])
        if index >= len(self.document["plan"]) or self.document["plan"][index] != {
            "protocol": protocol, "argv": argv,
        }:
            raise ValueError("local command differs from the fixed verification plan")
        log = self.path / f"{index:02d}.log"
        item = {
            "protocol": protocol, "argv": argv, "startedAt": _now(),
            "finishedAt": None, "returnCode": None, "error": None,
            "log": log.name, "bytes": None, "sha256": None,
        }
        self.document["commands"].append(item)
        self._save()
        print(f"    raw local log: {log}", flush=True)
        try:
            with log.open("xb") as stream:
                completed = subprocess.run(
                    argv, cwd=self.root, check=False,
                    stdout=stream, stderr=subprocess.STDOUT,
                )
                stream.flush()
                os.fsync(stream.fileno())
            item["returnCode"] = completed.returncode
            return completed
        except BaseException as error:
            item["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            item["finishedAt"] = _now()
            if log.exists():
                item.update(_digest(log))
            self._save()

    def finish(self, code: int, final: dict[str, Any], error: str | None = None) -> None:
        complete = (
            len(self.document["commands"]) == len(self.document["plan"])
            and all(item["returnCode"] == 0 and item["error"] is None
                    for item in self.document["commands"])
            and final == self.document["initial"]
            and self.document["environment"] is not None
            and self.document["environment"]["lockFileSha256"] == final["lockFileSha256"]
            and not final["fingerprint"]["dirty"]
        )
        self.document.update(
            finishedAt=_now(), final=final, error=error,
            result="passed" if code == 0 and complete and error is None else "failed",
        )
        self._save()


def check_bundle(
    path: Path, expected_plan: list[dict[str, Any]], expected_source: dict[str, Any],
    expected_cwd: Path, environment_fields: frozenset[str],
) -> dict[str, Any]:
    """Check recorded bytes and ordering; never authenticate, approve, or execute."""
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate bundle key")
            result[key] = value
        return result

    if path.resolve() != path.absolute():
        raise ValueError("bundle path must not traverse links")
    manifest = path / "manifest.json"
    if not stat.S_ISREG(manifest.lstat().st_mode):
        raise ValueError("bundle manifest must be a regular file")
    value = json.loads(manifest.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    errors = list(Draft202012Validator(_BUNDLE_SCHEMA).iter_errors(value))
    if errors:
        raise ValueError(f"invalid local diagnostic bundle: {errors[0].message}")
    if value["runId"] != path.name:
        raise ValueError("bundle directory and run ID disagree")
    if value["cwd"] != str(expected_cwd.resolve()):
        raise ValueError("recorded execution directory differs from checkout")
    plan, commands = value["plan"], value["commands"]
    if plan != expected_plan or len(commands) > len(plan):
        raise ValueError("unexpected local verification protocol order")
    if value["initial"] != expected_source:
        raise ValueError("local source or input locks differ from bundle")
    for index, item in enumerate(commands):
        if {"protocol": item["protocol"], "argv": item["argv"]} != plan[index]:
            raise ValueError("recorded command differs from plan")
        if item["log"] != f"{index:02d}.log":
            raise ValueError("noncanonical local log path")
        log = path / item["log"]
        if log.is_symlink():
            raise ValueError("local log must not be a link")
        if _digest(log) != {"bytes": item["bytes"], "sha256": item["sha256"]}:
            raise ValueError("local log bytes or hash differ")
    if value["result"] not in {"incomplete", "failed", "passed"}:
        raise ValueError("unsupported local verification result")
    if value["result"] == "incomplete":
        raise ValueError("local verification bundle is incomplete")
    if value["finishedAt"] is None or value["final"] is None:
        raise ValueError("finished bundle lacks final source snapshot")
    def timestamp(text: str) -> datetime:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("local timestamp requires a timezone")
        return parsed
    start, finish = timestamp(value["startedAt"]), timestamp(value["finishedAt"])
    previous = start
    for item in commands:
        if item["finishedAt"] is None:
            raise ValueError("finished bundle has an unfinished command")
        command_start, command_finish = timestamp(item["startedAt"]), timestamp(item["finishedAt"])
        if not previous <= command_start <= command_finish <= finish:
            raise ValueError("local timestamps are out of order")
        previous = command_finish
    if start > finish:
        raise ValueError("local timestamps are out of order")
    if value["result"] == "passed":
        if (len(commands) != len(plan) or value["environment"] is None
                or value["error"] is not None or value["initial"] != value["final"]
                or any(item["returnCode"] != 0 or item["error"] is not None
                       or item["finishedAt"] is None for item in commands)):
            raise ValueError("passing local bundle has incomplete or failed execution")
        if value["initial"]["fingerprint"]["dirty"]:
            raise ValueError("passing local bundle requires a clean source")
        environment = value["environment"]
        if set(environment) != environment_fields:
            raise ValueError("passing local bundle requires the full preflight environment")
        for field, item in environment.items():
            if field == "lockFileSha256":
                continue  # Validated by the structural schema above.
            if field == "rustVersionMeetsWorkspace":
                valid = item is True
            elif field == "pythonLockMismatches":
                valid = item == []
            elif field == "pythonLockStatus":
                valid = item == "match"
            else:
                valid = isinstance(item, str) and bool(item)
            if not valid:
                raise ValueError(f"invalid passing environment field: {field}")
        if environment["lockFileSha256"] != value["initial"]["lockFileSha256"]:
            raise ValueError("executed lock files differ from source snapshot")
    return value
