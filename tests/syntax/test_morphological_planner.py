import pytest

from app.domain.lexicon.models import LexicalEntity
from app.domain.syntax.csg import CSGEdge, CSGNode, ControlledSemanticGraph
from app.domain.syntax.feature_blackboard import FeatureBlackboard
from app.domain.syntax.morphological_planner import MorphologicalPlanner, PlannedWord
from app.domain.syntax.typology import TypologyMatrix


def _entity(concept: str, pos: str = "v.", ipa: str = "") -> LexicalEntity:
    return LexicalEntity(
        id=concept.lower(),
        concept=concept,
        pos=pos,
        ipa_current=ipa or concept.lower(),
        ipa_history=[],
        frequency_weight=0.5,
    )


def _lexmap(*entities: LexicalEntity) -> dict[str, LexicalEntity | None]:
    return {e.concept: e for e in entities}


def _make_svo_csg(
    agent_prime: str = "I",
    pred_prime: str = "SEE",
    patient_prime: str = "MAN",
    tense: str = "PAST",
    person: str = "1",
    number: str = "sg",
) -> ControlledSemanticGraph:
    csg = ControlledSemanticGraph()
    csg.add_node(CSGNode(id="subj", prime_id=agent_prime,
                         attributes={"person": person, "number": number}))
    csg.add_node(CSGNode(id="pred", prime_id=pred_prime,
                         attributes={"tense": tense}))
    csg.add_node(CSGNode(id="obj",  prime_id=patient_prime))
    csg.add_edge(CSGEdge(from_id="subj", to_id="pred", relation="agent"))
    csg.add_edge(CSGEdge(from_id="pred", to_id="obj",  relation="patient"))
    return csg


class TestPlannedWordSurface:
    def test_no_affixes(self):
        pw = PlannedWord(role="subject", lexeme_ipa="ni")
        assert pw.surface_ipa == "ni"

    def test_suffix_only(self):
        pw = PlannedWord(role="object", lexeme_ipa="min", suffixes=["o"])
        assert pw.surface_ipa == "mino"

    def test_prefix_and_suffix(self):
        pw = PlannedWord(role="verb", lexeme_ipa="vid", prefixes=["ga"], suffixes=["et"])
        assert pw.surface_ipa == "gavidet"

    def test_multiple_suffixes_ordered(self):
        pw = PlannedWord(role="verb", lexeme_ipa="vid", suffixes=["et", "m"])
        assert pw.surface_ipa == "videtm"


class TestMorphologicalPlannerSVO:
    def setup_method(self):
        self.typology = TypologyMatrix(
            word_order="SVO",
            tense_system="inflectional",
            morph_type="agglutinative",
            case_system="nominative_accusative",
            agreement_features=["person", "number"],
            morpheme_table={"ACC": "o", "PAST": "et", "1SG": "m", "3SG": "s"},
        )
        self.planner = MorphologicalPlanner(self.typology)

    def _run(self, csg, lexmap):
        board = FeatureBlackboard()
        return self.planner.plan(csg, lexmap, board)

    def test_three_planned_words_for_svo(self):
        csg = _make_svo_csg()
        lm = _lexmap(
            _entity("I", "pron.", "ni"),
            _entity("SEE", "v.", "vid"),
            _entity("MAN", "n.", "min"),
        )
        result = self._run(csg, lm)
        assert len(result) == 3

    def test_subject_has_no_accusative(self):
        csg = _make_svo_csg()
        lm = _lexmap(
            _entity("I", "pron.", "ni"),
            _entity("SEE", "v.", "vid"),
            _entity("MAN", "n.", "min"),
        )
        result = self._run(csg, lm)
        subj = next(w for w in result if w.role == "subject")
        assert "o" not in subj.suffixes

    def test_object_gets_accusative(self):
        csg = _make_svo_csg()
        lm = _lexmap(
            _entity("I", "pron.", "ni"),
            _entity("SEE", "v.", "vid"),
            _entity("MAN", "n.", "min"),
        )
        result = self._run(csg, lm)
        obj = next(w for w in result if w.role == "object")
        assert obj.surface_ipa == "mino"

    def test_verb_gets_past_suffix(self):
        csg = _make_svo_csg(tense="PAST")
        lm = _lexmap(
            _entity("I", "pron.", "ni"),
            _entity("SEE", "v.", "vid"),
            _entity("MAN", "n.", "min"),
        )
        result = self._run(csg, lm)
        verb = next(w for w in result if w.role == "verb")
        assert "et" in verb.suffixes

    def test_verb_gets_agreement_1sg(self):
        csg = _make_svo_csg(person="1", number="sg")
        lm = _lexmap(
            _entity("I", "pron.", "ni"),
            _entity("SEE", "v.", "vid"),
            _entity("MAN", "n.", "min"),
        )
        result = self._run(csg, lm)
        verb = next(w for w in result if w.role == "verb")
        assert "m" in verb.suffixes

    def test_blackboard_written_with_agent_features(self):
        csg = _make_svo_csg(person="1", number="sg")
        lm = _lexmap(
            _entity("I", "pron.", "ni"),
            _entity("SEE", "v.", "vid"),
            _entity("MAN", "n.", "min"),
        )
        board = FeatureBlackboard()
        self.planner.plan(csg, lm, board)
        assert board.read("person") == "1"
        assert board.read("number") == "sg"


class TestMorphologicalPlannerNoCase:
    def test_no_suffix_when_case_none(self):
        typology = TypologyMatrix(
            case_system="none",
            morpheme_table={"ACC": "o"},
        )
        planner = MorphologicalPlanner(typology)
        csg = _make_svo_csg()
        lm = _lexmap(
            _entity("I", "pron.", "ni"),
            _entity("SEE", "v.", "vid"),
            _entity("MAN", "n.", "min"),
        )
        board = FeatureBlackboard()
        result = planner.plan(csg, lm, board)
        obj = next(w for w in result if w.role == "object")
        assert obj.surface_ipa == "min"


class TestMorphologicalPlannerMissingLexEntry:
    def test_missing_predicate_skipped(self):
        typology = TypologyMatrix()
        planner = MorphologicalPlanner(typology)
        csg = _make_svo_csg()
        lm: dict[str, LexicalEntity | None] = {
            "I": _entity("I", "pron.", "ni"),
            "SEE": None,
            "MAN": _entity("MAN", "n.", "min"),
        }
        board = FeatureBlackboard()
        result = planner.plan(csg, lm, board)
        roles = [w.role for w in result]
        assert "verb" not in roles

    def test_missing_patient_skipped(self):
        typology = TypologyMatrix()
        planner = MorphologicalPlanner(typology)
        csg = _make_svo_csg()
        lm: dict[str, LexicalEntity | None] = {
            "I": _entity("I", "pron.", "ni"),
            "SEE": _entity("SEE", "v.", "vid"),
            "MAN": None,
        }
        board = FeatureBlackboard()
        result = planner.plan(csg, lm, board)
        roles = [w.role for w in result]
        assert "object" not in roles


class TestMorphologicalPlannerIsolating:
    def test_isolating_no_tense_suffix(self):
        typology = TypologyMatrix(
            tense_system="isolating",
            case_system="none",
            agreement_features=[],
            morpheme_table={"PAST": "le"},
        )
        planner = MorphologicalPlanner(typology)
        csg = _make_svo_csg(tense="PAST")
        lm = _lexmap(
            _entity("I", "pron.", "ni"),
            _entity("SEE", "v.", "vid"),
            _entity("MAN", "n.", "min"),
        )
        board = FeatureBlackboard()
        result = planner.plan(csg, lm, board)
        verb = next((w for w in result if w.role == "verb"), None)
        assert verb is not None
        assert verb.surface_ipa == "vid"
