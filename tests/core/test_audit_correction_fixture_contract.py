"""Planning-only contracts for the audit-correction regression fixtures.

These checks validate review vectors and exact legacy wire evidence. They do
not implement LanguageState v3, execute future Rust runners, repair the Python
legacy engine, or authorize a production writer.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from app.domain.lexicon.dag import WordDAG
from app.domain.lexicon.models import LexicalEntity
from app.domain.storage.canonical import canonical_json_bytes
from app.domain.storage.event_log import DeltaEvent, DeltaEventType, KeyframeManager
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.typology import TypologyMatrix
import tests.storage.test_history_replay_features as legacy_replay_tests


ROOT = Path(__file__).resolve().parents[2]
LINGUISTIC_FIXTURE_PATH = (
    ROOT / "tests" / "fixtures" / "linguistic_regression_cases_v1.json"
)
LEGACY_FIXTURE_PATH = (
    ROOT / "tests" / "fixtures" / "legacy_replay_migration_cases_v1.json"
)
RUST_HASH_PATH = ROOT / "crates" / "telysta-core" / "src" / "hash.rs"

LINGUISTIC_IDS = {
    "PH-N01", "PH-N02", "PH-N03", "PH-N04", "PH-N05", "PH-N06", "PH-P01",
    "CAP-N01", "CAT-N01", "LEX-N01", "HOM-N01", "HOM-N02", "MOR-N01",
    "MOR-N02", "SEM-N01", "SEM-N02", "VAL-N01", "VAL-N02", "QRY-N01",
    "DET-N01", "DATA-N01", "EVT-N01", "GRA-N01", "ANA-N01",
}
LEGACY_IDS = {f"LEGACY-REPLAY-{index:03d}" for index in range(1, 9)}
ASSUMPTION_CLASSES = {
    "hard_constraint",
    "empirical_prior",
    "research_hypothesis",
    "creative_preference",
}
CONTRACT_KINDS = {
    "software_invariant",
    "data_contract",
    "domain_well_formedness",
    "scientific_claim_boundary",
}
CLAIM_SCOPES = {
    "system_wide",
    "language_profile",
    "theory_profile",
    "fixture_only",
}
CASE_MODES = {
    "single_fault_negative",
    "positive_contract",
    "batch_diagnostic_coverage",
    "insufficient_evidence_bundle",
    "metamorphic_contract",
}
LINGUISTIC_CASE_FIELDS = {
    "fixtureId",
    "domain",
    "assumptionClass",
    "contractKind",
    "claimScope",
    "targetWorkPackage",
    "contractGate",
    "executionGate",
    "runnerBinding",
    "setup",
    "request",
    "oracle",
    "evidenceRefs",
}
LEGACY_CASE_FIELDS = {
    "fixtureId",
    "sourceTestNodeId",
    "sourceEnvelope",
    "declaredLegacyFailure",
    "migrationDisposition",
    "oracle",
    "retirement",
}
RETIREMENT_EVIDENCE = {
    "rust_target_contract_passing",
    "source_artifact_archived",
    "migration_report_recorded",
    "module_migration_matrix_updated",
    "migration_reviewer_approved",
}
BASE_FORBIDDEN_INFERENCES = {
    "legacy_event_as_v3_changeset",
    "state_diff_as_history",
    "silent_default",
    "broad_skip",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ENTITY_ID = re.compile(
    r"^telysta:(phoneme|feature|lexeme|sense|morpheme):"
    r"[a-z0-9](?:[a-z0-9-]{0,94}[a-z0-9])?$"
)
FIXTURE_REF = re.compile(
    r"^fixture:[a-z0-9][a-z0-9-]*(?::[a-z0-9][a-z0-9-]*)+$"
)
EVENT_FIELDS = {
    "event_type",
    "era",
    "word_id",
    "new_ipa",
    "old_ipa",
    "new_entity",
    "rule_name",
    "dag_parent_id",
    "source_language",
    "edge_type",
    "concept",
    "timestamp",
}
LEXICAL_ENTITY_FIELDS = {
    field_name for field_name in LexicalEntity.__dataclass_fields__
}
FORBIDDEN_SELF_REPORTED_KEYS = {
    "actual",
    "after",
    "before",
    "observed",
    "observedOutputHashes",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _cases_by_id(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = bundle["cases"]
    indexed = {case["fixtureId"]: case for case in cases}
    assert len(indexed) == len(cases)
    return indexed


def _walk(value: Any) -> list[Any]:
    values = [value]
    if isinstance(value, dict):
        for child in value.values():
            values.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_walk(child))
    return values


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in _walk(value) if isinstance(item, dict)]


def _wire_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _envelope_hash(envelope: dict[str, Any]) -> str:
    unhashed = copy.deepcopy(envelope)
    unhashed.pop("sourceEnvelopeSha256")
    return _canonical_json_sha256(unhashed)


def _event_from_payload(payload: dict[str, Any]) -> DeltaEvent:
    entity = payload["new_entity"]
    return DeltaEvent(
        event_type=DeltaEventType(payload["event_type"]),
        era=payload["era"],
        word_id=payload["word_id"],
        new_ipa=payload["new_ipa"],
        old_ipa=payload["old_ipa"],
        new_entity=LexicalEntity(**entity) if entity else None,
        rule_name=payload["rule_name"],
        dag_parent_id=payload["dag_parent_id"],
        source_language=payload["source_language"],
        edge_type=payload["edge_type"],
        concept=payload["concept"],
        timestamp=payload["timestamp"],
    )


def _normalise_platform_newlines(payload: bytes) -> bytes:
    return payload.replace(b"\r\n", b"\n")


def _assert_no_runner_observation_in_setup_or_request(case: dict[str, Any]) -> None:
    for section in ("setup", "request"):
        for item in _walk_dicts(case[section]):
            forbidden = FORBIDDEN_SELF_REPORTED_KEYS & set(item)
            assert not forbidden, (case["fixtureId"], section, forbidden)
            assert not any(key.startswith("observed") for key in item), (
                case["fixtureId"],
                section,
                item,
            )


def _segment_occurrences(value: Any) -> list[dict[str, Any]]:
    forms = [
        item
        for item in _walk_dicts(value)
        if item.get("kind") == "ordered_segment_occurrences"
    ]
    return [
        occurrence
        for form in forms
        for occurrence in form["occurrences"]
    ]


def _assert_semantic_contrast_oracles(case: dict[str, Any]) -> None:
    definitions = case["setup"]["readingDefinitions"]
    assert case["setup"]["equivalencePolicy"] == "fixture_structural_identity.v1"
    for contrast in case["request"]["contrasts"]:
        assert definitions[contrast["requiredReading"]] != definitions[contrast["candidateReading"]]
    controls = case["request"]["positiveControls"]
    assert controls
    assert case["oracle"]["positiveControlDecisions"] == {
        control["controlId"]: "accept" for control in controls
    }
    for control in controls:
        assert definitions[control["requiredReading"]] == definitions[control["candidateReading"]]


def test_semantic_contrasts_reject_identical_reading_mutation() -> None:
    baseline = _cases_by_id(_load(LINGUISTIC_FIXTURE_PATH))["SEM-N01"]
    _assert_semantic_contrast_oracles(baseline)
    for index in range(len(baseline["request"]["contrasts"])):
        mutant = copy.deepcopy(baseline)
        contrast = mutant["request"]["contrasts"][index]
        contrast["candidateReading"] = contrast["requiredReading"]
        with pytest.raises(AssertionError):
            _assert_semantic_contrast_oracles(mutant)
    mutant = copy.deepcopy(baseline)
    control = mutant["request"]["positiveControls"][0]
    control["candidateReading"] = "fixture:reading:quality-good"
    with pytest.raises(AssertionError):
        _assert_semantic_contrast_oracles(mutant)


def test_linguistic_fixture_protocol_is_closed_and_runner_facing() -> None:
    bundle = _load(LINGUISTIC_FIXTURE_PATH)
    assert set(bundle) == {
        "schemaVersion",
        "status",
        "sourcePlan",
        "fixtureIdPolicy",
        "fixtureProtocol",
        "resources",
        "cases",
    }
    assert bundle["schemaVersion"] == "telysta-linguistic-regression-cases.v1"
    assert bundle["status"] == "planning_only_not_a_production_persistence_format"
    assert bundle["fixtureIdPolicy"] == "immutable_once_merged"
    assert bundle["fixtureProtocol"] == {
        "identifierPolicy": "telysta_entity_ids_or_fixture_local_refs",
        "generatedObservationPolicy": "runner_only",
        "runnerStatus": "future_not_bound",
        "classificationAxes": [
            "assumptionClass",
            "contractKind",
            "claimScope",
        ],
        "bindingRequirements": [
            "versioned_adapter_schema",
            "accepted_baseline_before_negative_mutation",
            "explicit_single_fault_or_batch_case_mode",
            "runner_generated_diagnostics_only",
        ],
    }

    cases = _cases_by_id(bundle)
    assert set(cases) == LINGUISTIC_IDS
    for fixture_id, case in cases.items():
        assert set(case) == LINGUISTIC_CASE_FIELDS, fixture_id
        assert case["assumptionClass"] in ASSUMPTION_CLASSES
        assert case["contractKind"] in CONTRACT_KINDS
        assert case["claimScope"] in CLAIM_SCOPES
        assert re.fullmatch(r"G(?:0A|0B|[1-7])", case["contractGate"])
        assert re.fullmatch(r"G(?:0A|0B|[1-7])", case["executionGate"])
        assert case["runnerBinding"]["status"] == "future"
        assert case["runnerBinding"]["adapter"].endswith(".v1")
        assert case["runnerBinding"]["caseMode"] in CASE_MODES
        if case["claimScope"] == "theory_profile":
            assert case["assumptionClass"] == "research_hypothesis"
            assert case["contractKind"] in {
                "domain_well_formedness",
                "scientific_claim_boundary",
            }
        if case["contractKind"] in {"software_invariant", "data_contract"}:
            assert case["claimScope"] == "system_wide"
        assert case["oracle"]["decision"] in {
            "accept",
            "accept_with_ambiguity",
            "reject",
            "accept_with_loss",
        }
        diagnostics = case["oracle"]["diagnostics"]
        if case["oracle"]["decision"] == "reject":
            assert diagnostics, fixture_id
        mode = case["runnerBinding"]["caseMode"]
        if mode == "single_fault_negative":
            assert case["oracle"]["decision"] == "reject"
            assert len(diagnostics) == 1
        elif mode == "batch_diagnostic_coverage":
            assert case["oracle"]["decision"] == "reject"
            assert len(diagnostics) > 1
        elif mode == "insufficient_evidence_bundle":
            assert case["oracle"]["decision"] == "reject"
            assert len(diagnostics) == 1
        elif mode == "positive_contract":
            assert case["oracle"]["decision"] in {
                "accept",
                "accept_with_ambiguity",
            }
            assert not diagnostics
        elif mode == "metamorphic_contract":
            assert case["oracle"]["decision"] == "accept"
            assert not diagnostics
        assert all(item["code"].strip() for item in diagnostics)
        assert case["evidenceRefs"]
        for evidence_ref in case["evidenceRefs"]:
            relative_path, fragment = evidence_ref.split("#", maxsplit=1)
            evidence_path = ROOT / relative_path
            assert evidence_path.is_file(), (fixture_id, evidence_ref)
            evidence_text = evidence_path.read_text(encoding="utf-8")
            assert f'id="{fragment}"' in evidence_text, (fixture_id, evidence_ref)
        _assert_no_runner_observation_in_setup_or_request(case)


def test_linguistic_resource_ids_and_references_are_closed() -> None:
    bundle = _load(LINGUISTIC_FIXTURE_PATH)
    cases = _cases_by_id(bundle)
    resources = bundle["resources"]

    segments = resources["segmentRegistry"]["segments"]
    segment_ids = {segment["segmentId"] for segment in segments}
    assert len(segment_ids) == len(segments)
    assert all(ENTITY_ID.fullmatch(segment_id) for segment_id in segment_ids)
    for segment in segments:
        feature_ids = [feature["featureId"] for feature in segment["features"]]
        assert len(feature_ids) == len(set(feature_ids))
        assert all(ENTITY_ID.fullmatch(feature_id) for feature_id in feature_ids)
        assert all(
            feature["value"]["kind"] == "boolean"
            and isinstance(feature["value"]["value"], bool)
            for feature in segment["features"]
        )

    profile_refs = {
        profile["profileRef"] for profile in resources["phonotacticProfiles"]
    }
    language_profile_refs = {
        profile["profileRef"] for profile in resources["languageProfiles"]
    }
    assert all(FIXTURE_REF.fullmatch(ref) for ref in profile_refs | language_profile_refs)
    assert len(profile_refs) == len(resources["phonotacticProfiles"])
    assert len(language_profile_refs) == len(resources["languageProfiles"])

    unresolved_segments: dict[str, set[str]] = {}
    for fixture_id, case in cases.items():
        setup_profile = case["setup"].get("profileRef")
        if setup_profile is not None:
            assert setup_profile in profile_refs | language_profile_refs
        refs = {
            occurrence["segmentId"]
            for occurrence in _segment_occurrences(
                {"setup": case["setup"], "request": case["request"]}
            )
        }
        unresolved = refs - segment_ids
        if unresolved:
            unresolved_segments[fixture_id] = unresolved
    assert unresolved_segments == {
        "PH-N01": {"telysta:phoneme:unknown-x"}
    }


def test_phonology_cases_isolate_their_declared_error() -> None:
    bundle = _load(LINGUISTIC_FIXTURE_PATH)
    cases = _cases_by_id(bundle)
    profiles = {
        profile["profileRef"]: profile
        for profile in bundle["resources"]["phonotacticProfiles"]
    }

    ph_n01 = cases["PH-N01"]
    assert ph_n01["oracle"]["diagnostics"] == [
        {"code": "unknown_segment", "subjectRef": "telysta:phoneme:unknown-x"}
    ]
    assert any(
        occurrence["segmentId"] == "telysta:phoneme:a"
        for occurrence in ph_n01["request"]["form"]["occurrences"]
    )

    ph_n04 = cases["PH-N04"]
    form_ids = [
        occurrence["occurrenceId"]
        for occurrence in ph_n04["request"]["form"]["occurrences"]
    ]
    role_ids = [
        occurrence_id
        for syllable in ph_n04["request"]["proposedSyllables"]
        for role in ("onset", "nucleus", "coda")
        for occurrence_id in syllable[role]
    ]
    counts = {occurrence_id: role_ids.count(occurrence_id) for occurrence_id in form_ids}
    assert counts == {
        "fixture:occurrence:ph-n04-001": 1,
        "fixture:occurrence:ph-n04-002": 1,
        "fixture:occurrence:ph-n04-003": 2,
        "fixture:occurrence:ph-n04-004": 1,
    }
    profile = profiles[ph_n04["setup"]["profileRef"]]
    for syllable in ph_n04["request"]["proposedSyllables"]:
        assert len(syllable["onset"]) <= profile["maxOnsetSegments"]
        assert len(syllable["coda"]) <= profile["maxCodaSegments"]
    assert ph_n04["oracle"]["diagnostics"] == [
        {
            "code": "segment_occurrence_reused",
            "subjectRef": "fixture:occurrence:ph-n04-003",
        }
    ]

    ph_n05 = cases["PH-N05"]
    assert ph_n05["oracle"]["diagnostics"] == [
        {
            "code": "change_set_postcondition_invalid",
            "causeCode": "missing_licensed_nucleus",
        }
    ]
    assert {
        "history_head_unchanged",
        "semantic_hash_unchanged",
        "event_count_unchanged",
        "proposal_atomic",
    } == set(ph_n05["oracle"]["invariants"])

    candidate = cases["PH-N06"]["request"]["candidateProfile"]
    assert all(
        len(cluster) > candidate["maxOnsetSegments"]
        for cluster in candidate["licensedOnsetClusters"]
    )
    assert cases["PH-N06"]["oracle"]["diagnostics"] == [
        {"code": "licensed_cluster_exceeds_maximum_onset"}
    ]


def test_morphology_query_and_determinism_oracles_do_not_contain_observed_input() -> None:
    cases = _cases_by_id(_load(LINGUISTIC_FIXTURE_PATH))

    mor = cases["MOR-N01"]
    assert "analyses" not in mor["setup"]
    assert "analyses" not in mor["request"]
    cells = mor["setup"]["paradigmCells"]
    assert len(cells) == 2
    assert {
        cell["cellRef"] for cell in cells
    } == set(mor["oracle"]["result"]["analysisCellRefs"])
    for cell in cells:
        assert cell["morphOccurrences"]
        assert all(
            occurrence["realization"]["kind"] == "zero_exponent"
            and occurrence["realization"]["contributions"]
            for occurrence in cell["morphOccurrences"]
        )
        declared_features = {
            json.dumps(feature, sort_keys=True)
            for feature in cell["featureBundle"]
        }
        realized_features = {
            json.dumps(contribution, sort_keys=True)
            for occurrence in cell["morphOccurrences"]
            for contribution in occurrence["realization"]["contributions"]
        }
        assert realized_features <= declared_features
        assert len({
            occurrence["occurrenceId"]
            for occurrence in cell["morphOccurrences"]
        }) == len(cell["morphOccurrences"])

    query = cases["QRY-N01"]
    assert query["executionGate"] == "G2"
    assert query["request"]["queries"] == ["realize", "analyze", "evaluate"]
    assert set(query["oracle"]["observationsRequiredFromRunner"]) == {
        "semantic_hash",
        "history_head",
        "usage_corpus_hash",
        "event_count",
    }

    determinism = cases["DET-N01"]
    assert determinism["executionGate"] == "G2"
    assert determinism["targetWorkPackage"] == "WS1-05"
    assert determinism["setup"]["lockMaterialStatus"] == (
        "fixture_sentinel_pending_real_payload_binding"
    )
    assert determinism["request"]["baseline"] == {
        "replicateCount": 3,
        "executionIsolation": "fresh_process",
    }
    assert determinism["request"]["semanticMutation"]["kind"] == (
        "replace_semantic_field"
    )
    assert determinism["request"]["nonSemanticMutation"]["kind"] == (
        "replace_nonsemantic_field"
    )
    assert isinstance(determinism["setup"]["locks"]["rngRootSeed"], int)
    assert 0 <= determinism["setup"]["locks"]["rngRootSeed"] < 2**64
    assert determinism["setup"]["hashContract"]["hashKind"] == (
        "StateSemanticHash"
    )
    rust_hash_source = RUST_HASH_PATH.read_text(encoding="utf-8")
    schema_match = re.search(
        r'pub const SEMANTIC_HASH_SCHEMA: &str = "([^"]+)";',
        rust_hash_source,
    )
    assert schema_match is not None
    assert determinism["setup"]["hashContract"]["schema"] == schema_match.group(1)
    assert SHA256.fullmatch(
        determinism["setup"]["hashContract"]["coverageManifestSha256"]
    )
    assert set(
        determinism["oracle"]["observationsRequiredFromRunner"]
    ) == {
        "baseline_output_semantic_hashes",
        "semantic_mutant_output_semantic_hash",
        "nonsemantic_mutant_output_semantic_hash",
        "output_hash_kind",
        "output_hash_schema",
        "output_hash_coverage_manifest_sha256",
    }
    assert set(determinism["oracle"]["relations"]) == {
        "all_baseline_output_semantic_hashes_equal",
        "semantic_mutant_hash_differs_from_baseline",
        "nonsemantic_mutant_hash_equals_baseline",
        "hash_contract_matches_locked_schema_and_coverage",
    }
    for key, value in determinism["setup"]["locks"].items():
        if key.endswith("Sha256"):
            assert SHA256.fullmatch(value)


def test_identity_meaning_valency_and_event_oracles_check_input_structure() -> None:
    bundle = _load(LINGUISTIC_FIXTURE_PATH)
    cases = _cases_by_id(bundle)

    lex = cases["LEX-N01"]
    concept_refs = {
        concept["conceptRef"]
        for concept in lex["setup"]["comparativeConcepts"]
    }
    assert concept_refs == {
        "fixture:comparative-concept:fire",
        "fixture:comparative-concept:passion",
    }
    senses = {sense["senseId"]: sense for sense in lex["setup"]["senses"]}
    lexemes = lex["setup"]["lexemes"]
    assert len(lexemes) == 2
    assert len(lexemes[0]["senseIds"]) == 2
    assert {
        senses[sense_id]["conceptRef"]
        for sense_id in lexemes[0]["senseIds"]
    } == concept_refs
    fire_aligned_lexemes = {
        lexeme["lexemeId"]
        for lexeme in lexemes
        if any(
            senses[sense_id]["conceptRef"]
            == "fixture:comparative-concept:fire"
            for sense_id in lexeme["senseIds"]
        )
    }
    assert fire_aligned_lexemes == {
        "telysta:lexeme:fire-basic",
        "telysta:lexeme:ritual-fire",
    }

    hom = cases["HOM-N01"]
    assert len(hom["setup"]["wordForms"]) == 2
    assert len({
        form["lexemeId"] for form in hom["setup"]["wordForms"]
    }) == 2
    assert {
        form["surfaceFormRef"] for form in hom["setup"]["wordForms"]
    } == {hom["request"]["surfaceFormRef"]}
    assert set(hom["oracle"]["result"]["analysisLexemeIds"]) == {
        form["lexemeId"] for form in hom["setup"]["wordForms"]
    }

    hom_change_case = cases["HOM-N02"]
    hom_change = hom_change_case["request"]["soundChange"]
    assert hom_change["scope"]["kind"] == "language_structure"
    assert hom_change["environment"] == {"kind": "all_positions"}
    assert hom_change["applicationMode"] == "simultaneous_all_matches"
    assert not any("lexemeId" in item for item in _walk_dicts(hom_change))
    assert {
        "ruleRef",
        "proposalRef",
        "provenanceRef",
    } <= hom_change.keys()
    target_segment = hom_change["target"]["segmentId"]
    structurally_affected_lexemes = {
        form["lexemeId"]
        for form in hom_change_case["setup"]["lexemeForms"]
        if target_segment in form["segments"]
    }
    assert structurally_affected_lexemes == set(
        hom_change_case["oracle"]["result"]["changedLexemeIds"]
    )
    assert structurally_affected_lexemes == {
        "telysta:lexeme:see",
        "telysta:lexeme:day",
    }
    replacement_segment = hom_change["replacementSegmentId"]
    changed_forms = {
        form["lexemeId"]: tuple(
            replacement_segment if segment == target_segment else segment
            for segment in form["segments"]
        )
        for form in hom_change_case["setup"]["lexemeForms"]
    }
    homophone_groups: dict[tuple[str, ...], set[str]] = {}
    for lexeme_id, form in changed_forms.items():
        homophone_groups.setdefault(form, set()).add(lexeme_id)
    resulting_homophones = set().union(
        *(
            lexeme_ids
            for lexeme_ids in homophone_groups.values()
            if len(lexeme_ids) > 1
        )
    )
    assert resulting_homophones == set(
        hom_change_case["oracle"]["result"]["homophonousLexemeIds"]
    )

    semantic_contrasts = cases["SEM-N01"]["request"]["contrasts"]
    _assert_semantic_contrast_oracles(cases["SEM-N01"])
    assert {contrast["contrastId"] for contrast in semantic_contrasts} == {
        "bad-good",
        "below-above",
    }
    assert {
        diagnostic["subjectRef"]
        for diagnostic in cases["SEM-N01"]["oracle"]["diagnostics"]
    } == {contrast["contrastId"] for contrast in semantic_contrasts}

    role_mapping = {
        item["role"]: item["case"]
        for item in cases["VAL-N01"]["oracle"]["result"]["roleMappings"]
    }
    assert role_mapping == {"A": "ergative", "S": "absolutive", "P": "absolutive"}
    profile_b = next(
        profile
        for profile in bundle["resources"]["languageProfiles"]
        if profile["profileRef"] == cases["VAL-N01"]["setup"]["profileRef"]
    )
    assert profile_b["nominalCaseCoding"]["domain"] == (
        "independent_nominal_arguments"
    )
    assert profile_b["nominalCaseCoding"]["splitConditions"] == []
    assert {
        item["role"]: item["case"]
        for item in profile_b["nominalCaseCoding"]["roleMappings"]
    } == role_mapping

    proposed = cases["EVT-N01"]["request"]["proposedMappings"]
    diagnostics = cases["EVT-N01"]["oracle"]["diagnostics"]
    assert len(proposed) == len(diagnostics) == 3
    assert {item["mappingId"] for item in proposed} == {
        diagnostic["subjectRef"] for diagnostic in diagnostics
    }
    assert all(item["eventKind"] == "sound_change" for item in proposed)
    assert {item["mechanism"] for item in proposed} == {
        "grammaticalization",
        "analogy",
        "analogical_homophone_repair",
    }


def test_legacy_fixture_protocol_and_exact_xfail_mapping_are_closed() -> None:
    bundle = _load(LEGACY_FIXTURE_PATH)
    assert set(bundle) == {
        "schemaVersion",
        "status",
        "sourcePlan",
        "evidenceProtocol",
        "wireContract",
        "cases",
    }
    assert bundle["schemaVersion"] == "telysta-legacy-replay-migration-cases.v1"
    assert bundle["evidenceProtocol"] == {
        "caseMaterial": (
            "synthetic_minimal_reproduction_unless_rawArchiveRef_is_present"
        ),
        "executionEvidenceStatus": "not_attached",
        "requiredBeforeFixtureFreeze": [
            "reviewedSubjectCommit",
            "sourceRevision",
            "sourceTestRunId",
            "runnerEnvironment",
            "timestamp",
            "resultFingerprint",
        ],
        "rawArchiveRequiredBeforeMigrationGate": True,
    }
    assert bundle["wireContract"]["fieldNaming"] == "python_snake_case"
    assert bundle["wireContract"]["byteWriter"] == (
        "app.domain.storage.event_log.KeyframeManager"
    )
    assert bundle["wireContract"]["artifactBytes"] == {
        "encoding": "utf-8",
        "ensureAscii": False,
        "indent": 2,
        "lineEnding": "platform_native",
        "payloadSha256Normalization": "platform_native_to_lf",
        "trailingNewline": False,
    }
    assert bundle["wireContract"]["sourceEnvelopeHash"] == {
        "algorithm": "sha256",
        "canonicalizer": "app.domain.storage.canonical.canonical_json_bytes",
        "encoding": "utf-8",
        "ensureAscii": False,
        "sortObjectKeys": True,
        "separators": [",", ":"],
        "allowNonFiniteNumbers": False,
        "excludedRootFields": ["sourceEnvelopeSha256"],
        "scope": "planning_fixture_integrity_only_not_archive_or_semantic_hash",
    }
    assert bundle["wireContract"]["targetBoundaryContract"] == {
        "targetStatus": "planned_not_executed",
        "replayRootKind": "LegacyHistoryBoundary",
        "checkpointRole": "ImportedCheckpoint_payload_not_second_root",
        "cardinalityByDisposition": {
            "state_only_boundary": {
                "roots": 1,
                "checkpoints": 1,
                "legacyDerivedChangeSets": 0,
            },
            "state_only_boundary_with_loss": {
                "roots": 1,
                "checkpoints": 1,
                "legacyDerivedChangeSets": 0,
            },
            "needs_resolution_before_boundary": {
                "roots": 0,
                "checkpoints": 0,
                "legacyDerivedChangeSets": 0,
            },
            "decoder_contract_only": {
                "roots": 0,
                "checkpoints": 0,
                "legacyDerivedChangeSets": 0,
            },
        },
        "requiredEvidenceWhenBoundaryCreated": [
            "source_archive_raw_sha256",
            "state_only_mapping",
            "loss_report",
            "provenance_discontinuity",
        ],
        "forbiddenInference": "legacy_event_as_v3_changeset",
    }

    cases = _cases_by_id(bundle)
    assert set(cases) == LEGACY_IDS
    assert len({
        case["retirement"]["plannedRustTargetTest"] for case in cases.values()
    }) == len(cases)
    assert {
        fixture_id: case["migrationDisposition"]
        for fixture_id, case in cases.items()
    } == {
        "LEGACY-REPLAY-001": "state_only_boundary",
        "LEGACY-REPLAY-002": "needs_resolution_before_boundary",
        "LEGACY-REPLAY-003": "state_only_boundary",
        "LEGACY-REPLAY-004": "decoder_contract_only",
        "LEGACY-REPLAY-005": "state_only_boundary",
        "LEGACY-REPLAY-006": "state_only_boundary",
        "LEGACY-REPLAY-007": "state_only_boundary_with_loss",
        "LEGACY-REPLAY-008": "state_only_boundary_with_loss",
    }

    for fixture_id, case in cases.items():
        assert set(case) == LEGACY_CASE_FIELDS, fixture_id
        assert case["declaredLegacyFailure"]["outcome"] == "strict_xfail"
        assert case["declaredLegacyFailure"]["lostDomains"]
        assert BASE_FORBIDDEN_INFERENCES <= set(
            case["oracle"]["forbiddenInferences"]
        )
        assert case["retirement"]["rustTargetStatus"] == "planned_not_implemented"
        expected_cardinality = bundle["wireContract"]["targetBoundaryContract"][
            "cardinalityByDisposition"
        ][case["migrationDisposition"]]
        assert expected_cardinality["legacyDerivedChangeSets"] == 0
        if case["migrationDisposition"].startswith("state_only_boundary"):
            assert expected_cardinality == {
                "roots": 1,
                "checkpoints": 1,
                "legacyDerivedChangeSets": 0,
            }
        else:
            assert expected_cardinality == {
                "roots": 0,
                "checkpoints": 0,
                "legacyDerivedChangeSets": 0,
            }
        assert case["retirement"]["plannedRustTargetTest"].startswith(
            "crates/telysta-core/tests/legacy_replay_migration.rs::"
        )
        assert set(
            case["retirement"]["requiredEvidenceBeforeXfailRemoval"]
        ) == RETIREMENT_EVIDENCE

        node = case["sourceTestNodeId"].split("::", maxsplit=1)[1]
        function_name = node.split("[", maxsplit=1)[0]
        function = getattr(legacy_replay_tests, function_name)
        marks = getattr(function, "pytestmark", [])
        xfail_marks = [mark for mark in marks if mark.name == "xfail"]
        assert len(xfail_marks) == 1
        assert xfail_marks[0].kwargs["strict"] is True

        if "[" in node:
            param_id = node.removesuffix("]").split("[", maxsplit=1)[1]
            parametrize = next(mark for mark in marks if mark.name == "parametrize")
            generated_ids = {
                f"{event_type.value}-{edge_type}"
                for event_type, edge_type in parametrize.args[1]
            }
            assert param_id in generated_ids


def test_legacy_synthetic_artifacts_match_current_python_producer_wire(
    tmp_path: Path,
) -> None:
    cases = _cases_by_id(_load(LEGACY_FIXTURE_PATH))
    relative_paths: set[tuple[str, str]] = set()
    for fixture_id, case in cases.items():
        envelope = case["sourceEnvelope"]
        assert envelope["vectorKind"].strip()
        assert envelope["sourceEnvelopeSha256"] == _envelope_hash(envelope)
        assert SHA256.fullmatch(envelope["sourceEnvelopeSha256"])

        for artifact in envelope["artifacts"]:
            path_key = (fixture_id, artifact["relativePath"])
            assert path_key not in relative_paths
            relative_paths.add(path_key)
            expected_payload_hash = hashlib.sha256(
                _wire_bytes(artifact["payload"])
            ).hexdigest()
            assert artifact["payloadSha256"] == expected_payload_hash
            assert SHA256.fullmatch(artifact["payloadSha256"])

            payloads = (
                artifact["payload"]
                if artifact["kind"] == "event_batch"
                else [artifact["payload"]]
            )
            if artifact["kind"] in {"event_batch", "event_record"}:
                for payload in payloads:
                    assert set(payload) == EVENT_FIELDS
                    entity = payload["new_entity"]
                    if entity is not None:
                        assert set(entity) == LEXICAL_ENTITY_FIELDS
                        assert asdict(LexicalEntity(**entity)) == entity
                    event = _event_from_payload(payload)
                    assert event.to_dict() == payload

            if artifact["kind"] == "keyframe":
                snapshot = artifact["payload"]
                assert {"era", "lexicon", "dag"} <= set(snapshot)
                lexicon = {
                    word_id: LexicalEntity(**entity)
                    for word_id, entity in snapshot["lexicon"].items()
                }
                assert all(
                    asdict(lexicon[word_id]) == entity
                    for word_id, entity in snapshot["lexicon"].items()
                )
                dag = WordDAG.from_dict(snapshot["dag"])
                state = EngineHotState(
                    lexicon=lexicon,
                    current_era=snapshot["era"],
                    dag=dag,
                )
                typology = (
                    TypologyMatrix.from_dict(copy.deepcopy(snapshot["typology"]))
                    if "typology" in snapshot
                    else None
                )
                assert state.snapshot(typology=typology) == snapshot

            if artifact["kind"] in {"keyframe", "event_batch"}:
                output_dir = tmp_path / fixture_id / str(len(relative_paths))
                manager = KeyframeManager(output_dir)
                if artifact["kind"] == "keyframe":
                    manager.write_keyframe(artifact["payload"]["era"], artifact["payload"])
                else:
                    events = [
                        _event_from_payload(payload)
                        for payload in artifact["payload"]
                    ]
                    eras = {event.era for event in events}
                    assert len(eras) == 1
                    for event in events:
                        manager.record(event)
                    manager.flush_era(eras.pop())

                emitted = (output_dir / artifact["relativePath"]).read_bytes()
                assert not emitted.endswith((b"\n", b"\r"))
                if os.linesep == "\r\n":
                    assert b"\r\n" in emitted
                    assert emitted.replace(b"\r\n", b"").find(b"\n") == -1
                else:
                    assert b"\r\n" not in emitted
                normalised = _normalise_platform_newlines(emitted)
                assert normalised == _wire_bytes(artifact["payload"])
                assert hashlib.sha256(normalised).hexdigest() == artifact[
                    "payloadSha256"
                ]


def test_legacy_loss_vectors_do_not_invent_missing_history() -> None:
    cases = _cases_by_id(_load(LEGACY_FIXTURE_PATH))

    legacy_002 = cases["LEGACY-REPLAY-002"]
    persisted_002 = legacy_002["sourceEnvelope"]["artifacts"][0]["payload"]
    assert "swadesh_concepts" not in persisted_002
    assert legacy_002["sourceEnvelope"]["onlineOnlyEvidence"] == {
        "swadesh_concepts": ["fire", "water"],
        "notPresentInPersistedSnapshot": True,
    }
    assert legacy_002["migrationDisposition"] == (
        "needs_resolution_before_boundary"
    )

    legacy_004 = cases["LEGACY-REPLAY-004"]
    mutations = legacy_004["oracle"]["mutations"]
    assert {
        (mutation["kind"], mutation["jsonPointer"], mutation["decision"])
        for mutation in mutations
    } == {
        ("remove_required_field", "/dag_parent_id", "reject"),
        ("add_unknown_field", "/guessed_meaning", "reject"),
    }

    legacy_007 = cases["LEGACY-REPLAY-007"]
    events_007 = legacy_007["sourceEnvelope"]["artifacts"][1]["payload"]
    assert [event["event_type"] for event in events_007] == [
        "compound_spawn",
        "dag_edge_add",
    ]
    assert [event["dag_parent_id"] for event in events_007] == [
        "root_a",
        "root_b",
    ]
    assert not any(
        key in event
        for event in events_007
        for key in ("parents", "parent_roles", "ordered_parents")
    )
    assert legacy_007["migrationDisposition"] == (
        "state_only_boundary_with_loss"
    )
    assert "compound_parent_roles_unrecorded" in legacy_007["oracle"][
        "lossReportCodes"
    ]
    assert "synthesize_parent_roles" in legacy_007["oracle"][
        "forbiddenInferences"
    ]

    legacy_008 = cases["LEGACY-REPLAY-008"]
    assert legacy_008["sourceEnvelope"]["artifacts"] == []
    assert legacy_008["sourceEnvelope"]["vectorKind"] == (
        "declared_absence_claim_not_execution_evidence"
    )
    assert legacy_008["sourceEnvelope"]["absenceEvidence"][
        "matchingInjectWordEvents"
    ] == []
    assert _load(LEGACY_FIXTURE_PATH)["evidenceProtocol"][
        "executionEvidenceStatus"
    ] == "not_attached"
    assert "synthetic_inject_word_event" in legacy_008["oracle"][
        "forbiddenInferences"
    ]
