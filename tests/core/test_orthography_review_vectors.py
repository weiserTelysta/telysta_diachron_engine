"""Finite ADR-014 relation oracle; no production spelling/parser/normalizer.

Observations below are manufactured positive controls and hostile mutations,
not outputs of a language engine. Only five declared cases are covered.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pytest


PACK = Path(__file__).resolve().parents[1] / "fixtures/orthography_review_vectors_v1.json"
REVIEW_IDS = {"ORT-R04", "ORT-R09", "ORT-R15", "ORT-R16", "ORT-R20"}
OBSERVATION_SCHEMA = "telysta-orthography-review-observation-draft.v1"
QueryKey = tuple[str, tuple[str, ...]]


@dataclass(frozen=True)
class Reading:
    analysis: str
    word_form: str | None
    current_phonology: tuple[str, ...] | None


def _pack() -> dict:
    return json.loads(PACK.read_bytes())


def _cases() -> dict[str, dict]:
    pack = _pack()
    assert pack["status"] == "planning_only_mutable_not_frozen"
    assert pack["productionRunnerStatus"] == "future"
    protocol = pack["finiteReviewOracle"]
    assert protocol["schemaVersion"] == "telysta-finite-orthography-oracle-draft.v1"
    assert protocol["status"] == "planning_relation_checks_not_production_execution"
    assert protocol["equivalence"] == "exact_case_local_analysis_identity"
    assert len(protocol["caseIds"]) == len(REVIEW_IDS) and set(protocol["caseIds"]) == REVIEW_IDS
    cases = {case["id"]: case for case in pack["cases"]}
    assert len(cases) == len(pack["cases"]) == 22
    return {key: cases[key] for key in protocol["caseIds"]}


def _relation(case: dict) -> dict[QueryKey, tuple[Reading, ...]]:
    """Derive the finite truth relation from declarations, never observations."""
    given, required = case["given"], case["required"]
    relation: dict[QueryKey, tuple[Reading, ...]] = {}
    if case["id"] in {"ORT-R04", "ORT-R20"}:
        forms = given["forms"]
        assert len(forms) == 2
        assert len({form["wordForm"] for form in forms}) == len({form["analysis"] for form in forms}) == 2
        assert all(len(form["base"]) == 1 for form in forms)
        assert len({tuple(form["base"]) for form in forms}) == 2
        phonology_key = "phonemes" if case["id"] == "ORT-R04" else "phonologyAfter"
        assert forms[0][phonology_key] == forms[1][phonology_key]
        for form in forms:
            key = ("base", tuple(form["base"]))
            relation[key] = (Reading(form["analysis"], form["wordForm"], tuple(form[phonology_key])),)
        assert required["exactAnalysesByBase"] == {
            key[1][0]: [row.analysis for row in rows] for key, rows in relation.items()
        }
        if case["id"] == "ORT-R04":
            assert required["roundTripContainsOwnAnalysis"] is True
            for form in forms:
                assert required[form["wordForm"]] == form["base"]
        else:
            assert set(required["distinctWordForms"]) == {form["wordForm"] for form in forms}
            assert len(required["distinctWordForms"]) == 2
            assert required["distinctBasesRetained"] is True
            assert required["eachBaseParsesToOwnLicensedAnalysis"] is True
        assert required["everyAnalysisRespellsInputUnderSameLocks"] is True
        if case["id"] == "ORT-R20":
            assert forms[0]["phonologyBefore"] != forms[1]["phonologyBefore"]
            assert all(form["phonologyBefore"] != form["phonologyAfter"] for form in forms)
            assert required["bothResolveCurrentPhonology"] == forms[0]["phonologyAfter"]
            assert given["languageRevisionAfter"] == _pack()["finiteReviewOracle"]["locks"]["languageRevision"]
            assert given["orthographyRevision"] == _pack()["finiteReviewOracle"]["locks"]["orthographyRevision"]
        assert given["additionalSpellingMappings"] == []
        return relation

    analyses = given["licensedAnalyses"]
    mappings = given["spellingsByAnalysis"]
    assert len(analyses) == len(set(analyses)) and set(mappings) == set(analyses)
    assert not set(analyses) & set(given.get("forbiddenAnalyses", []))
    for analysis in analyses:
        assert mappings[analysis] == [given["input"]]
    key = ("text", (given["input"],))
    relation[key] = tuple(Reading(analysis, None, None) for analysis in analyses)
    if case["id"] == "ORT-R09":
        assert len(analyses) == 2 and given["ambiguityBudget"] >= len(analyses)
        assert set(required["analysisSet"]) == set(analyses) and len(required["analysisSet"]) == 2
        assert required["allowedSpellings"] == [given["input"]]
        assert required["ambiguityReported"] is True
    elif case["id"] == "ORT-R15":
        assert not analyses and required["successfulAnalyses"] == []
        assert required["outcome"] == "AnalysisGap"
    else:
        assert case["id"] == "ORT-R16" and 0 < given["ambiguityBudget"] < len(analyses)
        assert required["complete"] is False
        assert required["diagnostic"] == "ambiguity_or_search_budget_exhausted"
    return relation


def _query(key: QueryKey) -> dict:
    kind, value = key
    return {"kind": kind, "value": list(value) if kind == "base" else value[0]}


def _query_key(query: dict) -> QueryKey:
    assert set(query) == {"kind", "value"}
    kind, value = query["kind"], query["value"]
    if kind == "base":
        assert isinstance(value, list) and value and all(isinstance(item, str) for item in value)
        return kind, tuple(value)
    assert kind == "text" and isinstance(value, str)
    # The whole written artifact is one key; never split it into phonemes,
    # graphemes, clusters or morphological identities by character count.
    return kind, (value,)


def _budget(case: dict) -> int:
    value = case["given"].get("ambiguityBudget", _pack()["finiteReviewOracle"]["defaultAmbiguityBudget"])
    assert type(value) is int and value > 0
    return value


def assert_observation(case: dict, observation: dict, *, requested_input: QueryKey) -> None:
    """Check licensed readings, respelling, current phonology references and locks."""
    assert set(observation) == {
        "schemaVersion",
        "caseId",
        "input",
        "locks",
        "ambiguityBudget",
        "complete",
        "outcome",
        "diagnostics",
        "analyses",
    }
    assert observation["schemaVersion"] == OBSERVATION_SCHEMA and observation["caseId"] == case["id"]
    assert observation["locks"] == _pack()["finiteReviewOracle"]["locks"]
    assert type(observation["complete"]) is bool
    budget = _budget(case)
    assert type(observation["ambiguityBudget"]) is int and observation["ambiguityBudget"] == budget
    key = _query_key(observation["input"])
    assert key == requested_input
    licensed = {reading.analysis: reading for reading in _relation(case).get(key, ())}
    rows = observation["analyses"]
    assert isinstance(rows, list) and len(rows) <= budget
    ids = []
    for row in rows:
        assert set(row) == {"analysisId", "wordForm", "currentPhonology", "respelling"}
        identity = row["analysisId"]
        assert identity in licensed
        reading = licensed[identity]
        assert row["wordForm"] == reading.word_form
        expected_phonology = None if reading.current_phonology is None else list(reading.current_phonology)
        assert row["currentPhonology"] == expected_phonology
        assert _query_key(row["respelling"]) == key
        ids.append(identity)
    assert len(ids) == len(set(ids))
    if len(licensed) > budget:
        assert observation["complete"] is False
        assert observation["outcome"] == "BudgetExhausted"
        assert observation["diagnostics"] == ["ambiguity_or_search_budget_exhausted"]
    else:
        assert observation["complete"] is True and set(ids) == set(licensed)
        assert observation["outcome"] == ("AnalysisForest" if licensed else "AnalysisGap")
        assert observation["diagnostics"] == ([] if licensed else ["AnalysisGap"])


def _control(case: dict, key: QueryKey) -> dict[str, Any]:
    """Manufacture an explicit positive control; this is not a parser result."""
    readings = _relation(case).get(key, ())
    budget = _budget(case)
    exhausted = len(readings) > budget
    return {
        "schemaVersion": OBSERVATION_SCHEMA,
        "caseId": case["id"],
        "input": _query(key),
        "locks": copy.deepcopy(_pack()["finiteReviewOracle"]["locks"]),
        "ambiguityBudget": budget,
        "complete": not exhausted,
        "outcome": "BudgetExhausted" if exhausted else "AnalysisForest" if readings else "AnalysisGap",
        "diagnostics": ["ambiguity_or_search_budget_exhausted"] if exhausted else [] if readings else ["AnalysisGap"],
        "analyses": [
            {
                "analysisId": reading.analysis,
                "wordForm": reading.word_form,
                "currentPhonology": None if reading.current_phonology is None else list(reading.current_phonology),
                "respelling": _query(key),
            }
            for reading in readings[:budget]
        ],
    }


def test_finite_controls_preserve_all_licensed_readings_and_order_independence() -> None:
    for case in _cases().values():
        for key in _relation(case):
            control = _control(case, key)
            assert_observation(case, control, requested_input=key)
            control["analyses"].reverse()
            assert_observation(case, control, requested_input=key)


@pytest.mark.parametrize("case_id", ["ORT-R04", "ORT-R09", "ORT-R20"])
def test_supported_finite_controls_reject_always_gap_or_incomplete(case_id: str) -> None:
    case = _cases()[case_id]
    for key in _relation(case):
        for incomplete in (False, True):
            result = _control(case, key)
            result.update(
                analyses=[],
                complete=not incomplete,
                outcome="BudgetExhausted" if incomplete else "AnalysisGap",
                diagnostics=["ambiguity_or_search_budget_exhausted"] if incomplete else ["AnalysisGap"],
            )
            with pytest.raises(AssertionError):
                assert_observation(case, result, requested_input=key)


@pytest.mark.parametrize("case_id", ["ORT-R04", "ORT-R20"])
def test_homophones_cannot_cross_read_or_restore_old_pronunciation(case_id: str) -> None:
    case = _cases()[case_id]
    keys = list(_relation(case))
    key = keys[0]
    original = _control(case, key)
    other = _control(case, keys[1])["analyses"][0]
    for change in ("other", "universal", "respell", "word_form", "old_phones"):
        result = copy.deepcopy(original)
        row = result["analyses"][0]
        if change == "other":
            result["analyses"] = [copy.deepcopy(other)]
        elif change == "universal":
            result["analyses"].append(copy.deepcopy(other))
        elif change == "respell":
            row["respelling"] = _query(keys[1])
        elif change == "word_form":
            row["wordForm"] = other["wordForm"]
        else:
            row["currentPhonology"] = case["given"]["forms"][0].get("phonologyBefore", ["P-OLD"])
        with pytest.raises(AssertionError):
            assert_observation(case, result, requested_input=key)


def test_syncretism_rejects_missing_extra_duplicate_and_forbidden_readings() -> None:
    case = _cases()["ORT-R09"]
    key = next(iter(_relation(case)))
    original = _control(case, key)
    for change in ("missing", "forbidden", "duplicate"):
        result = copy.deepcopy(original)
        if change == "missing":
            result["analyses"].pop()
        elif change == "forbidden":
            result["analyses"][0]["analysisId"] = case["given"]["forbiddenAnalyses"][0]
        else:
            result["analyses"][1] = copy.deepcopy(result["analyses"][0])
        with pytest.raises(AssertionError):
            assert_observation(case, result, requested_input=key)


def test_unknown_input_requires_gap_and_budget_exhaustion_never_claims_completeness() -> None:
    cases = _cases()
    gap = cases["ORT-R15"]
    key = next(iter(_relation(gap)))
    result = _control(gap, key)
    assert_observation(gap, result, requested_input=key)
    result["analyses"] = [
        {"analysisId": "A-INVENTED", "wordForm": None, "currentPhonology": None, "respelling": _query(key)}
    ]
    with pytest.raises(AssertionError):
        assert_observation(gap, result, requested_input=key)
    case = cases["ORT-R16"]
    key = next(iter(_relation(case)))
    original = _control(case, key)
    assert_observation(case, original, requested_input=key)
    for change in ("complete", "diagnostic", "over_budget"):
        result = copy.deepcopy(original)
        if change == "complete":
            result.update(complete=True, outcome="AnalysisForest", diagnostics=[])
        elif change == "diagnostic":
            result["diagnostics"] = []
        else:
            result["analyses"].append(
                {"analysisId": "A-THREE", "wordForm": None, "currentPhonology": None, "respelling": _query(key)}
            )
        with pytest.raises(AssertionError):
            assert_observation(case, result, requested_input=key)


def test_observations_reject_stale_locks_unknown_fields_and_changed_budget() -> None:
    case = _cases()["ORT-R09"]
    key = next(iter(_relation(case)))
    original = _control(case, key)
    for field in original["locks"]:
        result = copy.deepcopy(original)
        result["locks"][field] = "OTHER"
        with pytest.raises(AssertionError):
            assert_observation(case, result, requested_input=key)

    for change in ("unknown", "budget", "bool_complete", "unknown_identity"):
        result = copy.deepcopy(original)
        if change == "unknown":
            result["rankerSaysValidated"] = True
        elif change == "budget":
            result["ambiguityBudget"] += 1
        elif change == "bool_complete":
            result["complete"] = 1
        else:
            result["analyses"][0]["analysisId"] = "A-UNKNOWN"
        with pytest.raises(AssertionError):
            assert_observation(case, result, requested_input=key)


def test_observation_cannot_replace_the_requested_input_with_an_unknown_gap() -> None:
    case = _cases()["ORT-R04"]
    requested = next(iter(_relation(case)))
    other = ("base", ("G-UNLICENSED",))
    observation = _control(case, other)
    assert_observation(case, observation, requested_input=other)
    with pytest.raises(AssertionError):
        assert_observation(case, observation, requested_input=requested)


def test_review_relation_cannot_silently_disagree_with_required_truth_or_omit_mapping() -> None:
    cases = _cases()
    mutants = []
    case = copy.deepcopy(cases["ORT-R04"])
    case["required"]["exactAnalysesByBase"]["G-C"] = ["A-B"]
    mutants.append(case)
    case = copy.deepcopy(cases["ORT-R09"])
    case["given"]["spellingsByAnalysis"].pop("A-TWO")
    mutants.append(case)
    case = copy.deepcopy(cases["ORT-R09"])
    case["required"]["analysisSet"] = ["A-ONE"]
    mutants.append(case)
    case = copy.deepcopy(cases["ORT-R16"])
    case["required"]["complete"] = True
    mutants.append(case)
    case = copy.deepcopy(cases["ORT-R20"])
    case["required"]["bothResolveCurrentPhonology"] = ["P-1"]
    mutants.append(case)
    case = copy.deepcopy(cases["ORT-R20"])
    case["given"]["orthographyRevision"] = "O-STALE"
    mutants.append(case)
    for case in mutants:
        with pytest.raises(AssertionError):
            _relation(case)
