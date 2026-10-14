"""Hostile checks for mutable ADR-012 review bytes, never package writes."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.project_authority_review import (
    DOMAIN, FIXTURE_PATH, PROFILE, ROOT_FIELDS, SCHEMA_PATH, SELF_FIELD,
    authority_hash, canonical_manifest, parse_manifest, validate_manifest,
    verify_manifest, verify_vectors,
)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _manifest(index: int = 0) -> dict:
    return parse_manifest(_fixture()["vectors"][index]["rawManifestJson"].encode("utf-8"))


def test_review_known_answers_match_fixed_bytes_and_fake_input_preimages() -> None:
    assert verify_vectors() == ["AUTH-NATIVE", "AUTH-LEGACY-UNICODE"]
    assert [v["sha256"] for v in _fixture()["vectors"]] == [
        "04e1b6dfbb62a194ca838c570a5491831ee5ea04db3f02586dffc8e006b14dae",
        "5b583adf44cb5ef1ac7103be2277f219e68952e71a82f82557e3f4780c094605",
    ]


def test_review_hash_excludes_only_root_self_and_still_requires_checksum_match() -> None:
    manifest = _manifest()
    expected = authority_hash(manifest)
    for self_hash in ("0" * 64, "f" * 64, expected):
        manifest[SELF_FIELD] = self_hash
        assert authority_hash(manifest) == expected
        raw = json.dumps(manifest).encode()
        if self_hash == expected:
            assert verify_manifest(raw) == expected
        else:
            with pytest.raises(ValueError, match="mismatch"):
                verify_manifest(raw)
    del manifest[SELF_FIELD]
    with pytest.raises(ValueError):
        authority_hash(manifest)


def test_review_profile_covers_all_manifest_fields_and_explicit_nulls() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())["$defs"]["projectManifest"]
    native, legacy = _manifest(), _manifest(1)
    canonical = json.loads(canonical_manifest(native))
    assert set(canonical) == set(schema["properties"]) - {SELF_FIELD}
    assert set(native) == set(schema["required"]) == set(schema["properties"])
    baseline = authority_hash(native)
    changed = []
    for field in ROOT_FIELDS:
        mutation = copy.deepcopy(native)
        mutation[field] = "f" * 64
        changed.append(mutation)
    for field in ("historyHeads", "stateSemanticHashes"):
        mutation = copy.deepcopy(native)
        mutation[field]["main"] = "f" * 64
        changed.append(mutation)
    project = copy.deepcopy(native)
    project["projectId"] = "telysta:project:other"
    changed.append(project)
    branches = copy.deepcopy(native)
    for field in ("historyHeads", "stateSemanticHashes"):
        branches[field]["branch"] = branches[field].pop("main")
    changed.append(branches)
    migration = copy.deepcopy(native)
    migration["migrationMetadata"] = legacy["migrationMetadata"]
    changed.append(migration)
    for mutation in changed:
        assert authority_hash(mutation) != baseline
    for field in ("sourceSchema", "sourceArtifactSha256", "migrationId"):
        mutation = copy.deepcopy(legacy)
        mutation["migrationMetadata"][field] = "f" * 64
        assert authority_hash(mutation) != authority_hash(legacy)
    for field in ("schemaVersion", "authorityHashSchema"):
        mutation = copy.deepcopy(native)
        mutation[field] += ".unknown"
        with pytest.raises(ValueError):
            authority_hash(mutation)
    assert PROFILE.encode() + b"\0" == DOMAIN
    assert hashlib.sha256(canonical_manifest(native)).hexdigest() != baseline


def test_review_representation_order_and_escaping_do_not_change_hash() -> None:
    manifest = _manifest(1)
    reverse = dict(reversed(list(manifest.items())))
    for field in ("historyHeads", "stateSemanticHashes", "migrationMetadata"):
        reverse[field] = dict(reversed(list(reverse[field].items())))
    expected = authority_hash(manifest)
    for ascii_only in (False, True):
        for indent in (None, 2):
            raw = json.dumps(reverse, ensure_ascii=ascii_only, indent=indent).encode("utf-8")
            assert verify_manifest(raw) == expected
    canonical = canonical_manifest(manifest).decode("utf-8")
    # UTF-16 ordering puts the supplementary character before U+E000;
    # Python/Rust default scalar/UTF-8 ordering would get this wrong.
    assert canonical.index('"𐀀"') < canonical.index('"\ue000"')
    assert "\\u0000" in canonical and "\\t" in canonical and "\\b" in canonical
    assert "\\f" in canonical and "\\n" in canonical and "\\r" in canonical
    assert "\u2028" in canonical and "\u2029" in canonical
    assert not canonical.endswith("\n")
    assert "é" in canonical and "e\u0301" in canonical


def test_review_unicode_normalization_and_branch_binding_are_not_guessed() -> None:
    native = _manifest()
    variants = []
    for spelling in ("é", "e\u0301"):
        changed = copy.deepcopy(native)
        for field in ("historyHeads", "stateSemanticHashes"):
            changed[field][spelling] = changed[field].pop("main")
        variants.append(changed)
    assert authority_hash(variants[0]) != authority_hash(variants[1])
    for field in ("historyHeads", "stateSemanticHashes"):
        changed = copy.deepcopy(native)
        changed[field]["other"] = changed[field].pop("main")
        with pytest.raises(ValueError, match="key sets"):
            authority_hash(changed)


@pytest.mark.parametrize("raw", [
    b'{"a":"x","a":"y"}', b'{"a":"x","\\u0061":"y"}',
    b'{"a":{"b":null,"b":null}}', b'{"a":"\\ud800"}',
    b'{"\\udfff":null}', b'\xef\xbb\xbf{}', b'{"a":"\xff"}',
    b'{"a":1}', b'{"a":1.0}', b'{"a":NaN}', b'{"a":Infinity}',
    b'{"a":true}', b'{"a":false}', b'{"a":[]}', b'null', b'{} {}',
])
def test_review_raw_parser_rejects_lossy_or_out_of_profile_inputs(raw: bytes) -> None:
    with pytest.raises((ValueError, UnicodeDecodeError)):
        parse_manifest(raw)


def test_review_closed_schema_rejects_missing_unknown_non_scalar_and_bad_hash_fields() -> None:
    base = _manifest()
    invalid = []
    for field in base:
        item = copy.deepcopy(base)
        del item[field]
        invalid.append(item)
    for field in ("uiState", "jobs", "staging", "recoveryRecord", "detachedReceipt"):
        item = copy.deepcopy(base)
        item[field] = None
        invalid.append(item)
    item = copy.deepcopy(base)
    item["migrationMetadata"][SELF_FIELD] = "0" * 64
    invalid.append(item)
    for value in ("f" * 64 + "\n", "F" * 64, "0" * 63, "0" * 65, None, 0, True, [], "\ud800"):
        item = copy.deepcopy(base)
        item["eventStoreRootSha256"] = value
        invalid.append(item)
    item = copy.deepcopy(base)
    item["projectId"] += "\n"
    invalid.append(item)
    item = copy.deepcopy(base)
    item["historyHeads"][""] = item["historyHeads"].pop("main")
    invalid.append(item)
    invalid.append({None: "value"})
    for manifest in invalid:
        with pytest.raises(ValueError):
            validate_manifest(manifest)


def test_review_vector_verifier_detects_edited_expected_bytes_digest_and_input(tmp_path: Path) -> None:
    mutations = []
    for field in ("canonicalJson", "sha256", "rawManifestJson"):
        item = _fixture()
        item["vectors"][0][field] += "x"
        mutations.append(item)
    item = _fixture()
    item["vectors"][0]["hashInputs"][0]["rawUtf8"] += "x"
    mutations.append(item)
    item = _fixture()
    item["vectors"][0]["hashInputs"].pop()
    mutations.append(item)
    item = _fixture()
    item["vectors"][0]["hashInputs"][0]["kind"] = "production"
    mutations.append(item)
    item = _fixture()
    item["vectors"].append(copy.deepcopy(item["vectors"][0]))
    mutations.append(item)
    item = _fixture()
    item["vectors"] = []
    mutations.append(item)
    for mutation in mutations:
        path = tmp_path / "edited-vectors.json"
        path.write_text(json.dumps(mutation), encoding="utf-8")
        with pytest.raises(ValueError):
            verify_vectors(path)
