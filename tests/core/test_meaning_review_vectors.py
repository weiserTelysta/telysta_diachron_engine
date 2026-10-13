"""Finite planning-oracle checks, not a production Meaning IR or analyzer."""

from __future__ import annotations

import copy
from itertools import product
import json
from pathlib import Path

import pytest


PACK = Path(__file__).resolve().parents[1] / "fixtures" / "meaning_review_vectors_v1.json"


def cases() -> dict:
    pack = json.loads(PACK.read_bytes())
    assert pack["status"] == "mutable_planning_only"
    assert pack["runnerBinding"] == "future_not_bound"
    return {case["fixtureId"]: case for case in pack["cases"]}


def alpha_key(node: list, binders: tuple[str, ...] = ()) -> tuple:
    """Use lexical binder distance; never rename free constants or predicates."""
    op, *args = node
    if op in {"forall", "exists"}:
        binder, domain, body = args
        return op, domain, alpha_key(body, (binder, *binders))
    if op == "not":
        return op, alpha_key(args[0], binders)
    terms = []
    for kind, value in args:
        if kind == "var":
            if value not in binders:
                raise ValueError("free review variable")
            terms.append((kind, binders.index(value)))
        elif kind == "const":
            terms.append((kind, value))
        else:
            raise ValueError("unknown review term")
    return op, tuple(terms)


def truth(node: list, model: dict, bindings: dict | None = None) -> bool:
    bindings = {} if bindings is None else bindings
    op, *args = node
    if op == "not":
        return not truth(args[0], model, bindings)
    if op in {"forall", "exists"}:
        binder, domain, body = args
        values = [truth(body, model, {**bindings, binder: value}) for value in model["domains"][domain]]
        return all(values) if op == "forall" else any(values)
    terms = [bindings[value] if kind == "var" else value for kind, value in args]
    return terms in model["relations"][op]


def intent_key(value: dict) -> str:
    normalized = copy.deepcopy(value)
    normalized["commitments"] = sorted(normalized["commitments"], key=lambda item: json.dumps(item, sort_keys=True))
    return json.dumps(normalized, sort_keys=True)


def commitment_contract(case: dict) -> None:
    expected = {("s", "p", "presupposed"), ("s", "q", "asserted")}
    for baseline in (case["required"], case["equivalent"]):
        assert baseline["speechAct"] == "assert" and baseline["speaker"] == "s"
        assert baseline["atIssue"] == ["q"]
        tuples = [(item["holder"], item["proposition"], item["status"]) for item in baseline["commitments"]]
        assert len(tuples) == len(expected) and set(tuples) == expected


def question_contract(case: dict) -> None:
    assertion, *questions = case["forbidden"]
    for question in (case["required"], case["equivalent"], *questions):
        assert question["speechAct"] == "polarQuestion" and question["speaker"] == "s"
        assert question["commitments"] == []
        assert len(question["issue"]) == 2
        assert question["issue"][1] == ["not", question["issue"][0]]
    witness = case["witness"]
    assert witness["propositionDesignators"] == {"p": ["P0"]}
    assert truth(["P0"], witness) is False
    assert witness["requiredPositiveAlternativeTruth"] is True
    assert truth(case["required"]["issue"][0], witness) is witness["requiredPositiveAlternativeTruth"]
    expected = witness["forbiddenQuestionPositiveAlternativeTruth"]
    assert expected == [False, False]
    for question, label in zip(questions, expected, strict=True):
        assert truth(question["issue"][0], witness) is label
    assert assertion["speechAct"] == "assert" and assertion["commitments"]


@pytest.mark.parametrize("identifier", ["M-SCOPE-NEG", "M-SCOPE-QUANT"])
def test_scope_witnesses_separate_foils_and_allow_alpha_renaming(identifier: str) -> None:
    case = cases()[identifier]
    assert alpha_key(case["required"]) == alpha_key(case["equivalent"])
    assert truth(case["required"], case["witness"]) is case["witness"]["requiredTruth"]
    for foil, expected in zip(case["forbidden"], case["witness"]["forbiddenTruth"], strict=True):
        assert alpha_key(case["required"]) != alpha_key(foil)
        assert truth(foil, case["witness"]) is expected
        assert expected is not case["witness"]["requiredTruth"]


@pytest.mark.parametrize("identifier", ["M-SCOPE-NEG", "M-SCOPE-QUANT"])
def test_alpha_controls_hold_for_all_small_relation_assignments(identifier: str) -> None:
    case = cases()[identifier]
    model = copy.deepcopy(case["witness"])
    if identifier == "M-SCOPE-NEG":
        predicate, possible = "P", [["a"], ["b"]]
    else:
        predicate = "Transfer"
        possible = [[d, "theme0", r] for d in model["domains"]["donors"] for r in model["domains"]["recipients"]]
    for switches in product((False, True), repeat=len(possible)):
        model["relations"][predicate] = [edge for edge, on in zip(possible, switches, strict=True) if on]
        assert truth(case["required"], model) == truth(case["equivalent"], model)


def test_alpha_policy_rejects_capture_role_swap_and_constant_replacement() -> None:
    case = cases()["M-SCOPE-QUANT"]
    baseline = alpha_key(case["required"])
    for mutation in ("capture", "roles", "constant", "domain"):
        node = copy.deepcopy(case["equivalent"])
        atom = node[3][3]
        if mutation == "capture":
            atom[3] = ["var", "u"]
        elif mutation == "roles":
            atom[1], atom[3] = atom[3], atom[1]
        elif mutation == "constant":
            atom[2] = ["const", "other-theme"]
        else:
            node[2] = "other-donors"
        assert alpha_key(node) != baseline
    with pytest.raises(ValueError, match="free review variable"):
        alpha_key(["P", ["var", "unbound"]])


def test_same_scene_truth_does_not_erase_commitment_status() -> None:
    case = cases()["M-COMMITMENT"]
    commitment_contract(case)
    assert case["context"]["sceneTruth"] == {"p": True, "q": True}
    assert case["context"]["licensedPresuppositions"] == ["p"]
    assert intent_key(case["required"]) == intent_key(case["equivalent"])
    assert all(intent_key(case["required"]) != intent_key(foil) for foil in case["forbidden"])
    promoted = case["forbidden"][0]
    assert promoted["atIssue"] == ["p", "q"]
    assert {item["status"] for item in promoted["commitments"]} == {"asserted"}


def test_neutral_question_preserves_report_content_source_and_act() -> None:
    case = cases()["M-QUESTION-REPORT"]
    question_contract(case)
    required = case["required"]
    assert required["speechAct"] == "polarQuestion" and required["commitments"] == []
    assert required["issue"][1] == ["not", required["issue"][0]]
    assert intent_key(required) == intent_key(case["equivalent"])
    assert truth(required["issue"][0], case["witness"]) is True
    assertion, direct_question, other_source = case["forbidden"]
    assert assertion["speechAct"] == "assert" and assertion["commitments"]
    assert truth(assertion["content"], case["witness"]) is True
    for foil in (direct_question, other_source):
        assert truth(foil["issue"][0], case["witness"]) is False
    assert all(intent_key(required) != intent_key(foil) for foil in case["forbidden"])


def test_review_oracles_reject_lost_commitment_malformed_question_and_false_labels() -> None:
    original = cases()
    commitment = copy.deepcopy(original["M-COMMITMENT"])
    for key in ("required", "equivalent"):
        commitment[key]["commitments"] = [item for item in commitment[key]["commitments"] if item["proposition"] != "p"]
    with pytest.raises(AssertionError):
        commitment_contract(commitment)
    question = copy.deepcopy(original["M-QUESTION-REPORT"])
    question["forbidden"][2]["issue"][1] = copy.deepcopy(question["required"]["issue"][1])
    with pytest.raises(AssertionError):
        question_contract(question)
    question = copy.deepcopy(original["M-QUESTION-REPORT"])
    question["witness"]["requiredPositiveAlternativeTruth"] = False
    question["witness"]["forbiddenQuestionPositiveAlternativeTruth"] = [True, True]
    with pytest.raises(AssertionError):
        question_contract(question)
