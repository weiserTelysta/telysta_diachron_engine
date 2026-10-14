"""Read-only ADR-012 hash research; never reads or writes a project package.

This restricted JCS profile is mutable review material, not a production
canonicalizer, object-graph validator, or persistence format.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PROFILE = "telysta-project-authority-hash-draft.v1"
DOMAIN = PROFILE.encode("ascii") + b"\0"
SCHEMA_PATH = ROOT / "docs/ADR_011_SCHEMA_DRAFT_V1.json"
FIXTURE_PATH = ROOT / "tests/fixtures/project_authority_hash_review_v1.json"
SELF_FIELD = "projectAuthorityHash"
HASH = re.compile(r"[0-9a-f]{64}")
PROJECT_ID = re.compile(r"telysta:project:[a-z0-9](?:[a-z0-9-]{0,94}[a-z0-9])?")
ROOT_FIELDS = (
    "eventStoreRootSha256", "runLedgerHeadSha256",
    "usageCorpusRootSha256", "dependencyBundleRootSha256",
)


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_number(token: str) -> Any:
    raise ValueError(f"numbers/non-JSON constants are outside this profile: {token}")


def _validate_strings(value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise ValueError("unpaired surrogate") from error
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("object keys must be strings")
            _validate_strings(key)
            _validate_strings(item)
        return
    raise ValueError("only objects, strings and null are allowed by this profile")


def parse_manifest(raw: bytes) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is not allowed")
    value = json.loads(
        raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_pairs,
        parse_int=_reject_number, parse_float=_reject_number,
        parse_constant=_reject_number,
    )
    _validate_strings(value)
    if not isinstance(value, dict):
        raise ValueError("manifest must be an object")
    return value


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate shape and local relationships, not replay or reachable objects."""
    _validate_strings(manifest)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator({
        "$ref": "#/$defs/projectManifest", "$defs": schema["$defs"],
    })
    errors = list(validator.iter_errors(manifest))
    if errors:
        raise ValueError(errors[0].message)
    if PROJECT_ID.fullmatch(manifest["projectId"]) is None:
        raise ValueError("invalid project ID")
    if manifest["authorityHashSchema"] != PROFILE:
        raise ValueError("unsupported authority hash profile")
    heads, states = manifest["historyHeads"], manifest["stateSemanticHashes"]
    if set(heads) != set(states):
        raise ValueError("state/history branch key sets differ")
    hashes = [manifest[field] for field in (*ROOT_FIELDS, SELF_FIELD)]
    hashes.extend(heads.values())
    hashes.extend(states.values())
    source = manifest["migrationMetadata"]["sourceArtifactSha256"]
    if source is not None:
        hashes.append(source)
    if any(HASH.fullmatch(value) is None for value in hashes):
        raise ValueError("invalid SHA-256 syntax")


def _canonical(value: Any) -> str:
    if isinstance(value, dict):
        keys = sorted(value, key=lambda key: key.encode("utf-16-be"))
        return "{" + ",".join(_canonical(key) + ":" + _canonical(value[key]) for key in keys) + "}"
    # Strings/null only, already checked. Python's escaping matches the
    # RFC 8785 string rules on Unicode scalar values; no numbers are serialized.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def canonical_manifest(manifest: dict[str, Any]) -> bytes:
    validate_manifest(manifest)
    return _canonical({key: value for key, value in manifest.items() if key != SELF_FIELD}).encode("utf-8")


def authority_hash(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(DOMAIN + canonical_manifest(manifest)).hexdigest()


def verify_manifest(raw: bytes) -> str:
    manifest = parse_manifest(raw)
    digest = authority_hash(manifest)
    if digest != manifest[SELF_FIELD]:
        raise ValueError("projectAuthorityHash mismatch")
    return digest


def verify_vectors(path: Path = FIXTURE_PATH) -> list[str]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    if fixture["schemaVersion"] != "telysta-project-authority-review-vectors-draft.v1":
        raise ValueError("unsupported review fixture")
    if fixture["status"] != "mutable_review_not_production_evidence" or fixture["profile"] != PROFILE:
        raise ValueError("invalid review boundary/profile")
    verified = []
    if not fixture["vectors"]:
        raise ValueError("review vectors must not be empty")
    for vector in fixture["vectors"]:
        if vector["id"] in verified:
            raise ValueError("duplicate vector ID")
        manifest = parse_manifest(vector["rawManifestJson"].encode("utf-8"))
        canonical = canonical_manifest(manifest)
        if canonical != vector["canonicalJson"].encode("utf-8"):
            raise ValueError("canonical bytes differ from known answer")
        if authority_hash(manifest) != vector["sha256"]:
            raise ValueError("digest differs from known answer")
        verify_manifest(vector["rawManifestJson"].encode("utf-8"))
        inputs = vector["hashInputs"]
        for item in inputs:
            if item["kind"] != "fake_review_preimage_not_domain_payload":
                raise ValueError("review preimages must not claim domain validity")
            if hashlib.sha256(item["rawUtf8"].encode("utf-8")).hexdigest() != item["sha256"]:
                raise ValueError("review input bytes/hash mismatch")
        roots = {manifest[field] for field in ROOT_FIELDS}
        roots.update(manifest["historyHeads"].values())
        roots.update(manifest["stateSemanticHashes"].values())
        source = manifest["migrationMetadata"]["sourceArtifactSha256"]
        if source is not None:
            roots.add(source)
        if roots != {item["sha256"] for item in inputs} or len(inputs) != len(roots):
            raise ValueError("review preimages do not cover exactly the manifest input hashes")
        verified.append(vector["id"])
    return verified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vectors", type=Path, default=FIXTURE_PATH)
    args = parser.parse_args()
    verified = verify_vectors(args.vectors)
    print(json.dumps({
        "schemaVersion": "telysta-project-authority-review-report.v1",
        "status": "research_only_not_graph_or_gate_validation",
        "profile": PROFILE, "verifiedVectors": verified,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
