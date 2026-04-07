import pytest

from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.backends.native_backend import NativeBackend
from app.domain.phonology.operators.final_vowel_drop import FinalVowelDropOperator
from app.domain.phonology.operators.registry import OperatorRegistry
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.csg import CSGEdge, CSGNode, ControlledSemanticGraph
from app.domain.syntax.pipeline import CSGPipeline, GenerationResult
from app.domain.syntax.semantic_graph import SemanticGraph, SemanticPrime
from app.domain.syntax.typology import TypologyMatrix


def _prime_graph() -> SemanticGraph:
    g = SemanticGraph()
    for pid in ["I", "SEE", "MAN", "GOOD", "WATER"]:
        g.add_prime(SemanticPrime(id=pid, label_en=pid.lower(),
                                  category="test", relations=()))
    return g


def _entity(concept: str, pos: str, ipa: str) -> LexicalEntity:
    return LexicalEntity(
        id=concept.lower(), concept=concept, pos=pos,
        ipa_current=ipa, ipa_history=[], frequency_weight=0.5,
    )


def _hot_state(*entities: LexicalEntity) -> EngineHotState:
    hs = EngineHotState()
    for e in entities:
        hs.put(e)
    return hs


def _registry_no_ops() -> tuple[OperatorRegistry, PhonemeInventory]:
    inv = PhonemeInventory.from_preset("ipa_minimal")
    reg = OperatorRegistry()
    return reg, inv


def _registry_with_fvd() -> tuple[OperatorRegistry, PhonemeInventory]:
    inv = PhonemeInventory.from_preset("ipa_minimal")
    backend = NativeBackend()
    op = FinalVowelDropOperator(backend=backend, inventory=inv, era_start=0)
    reg = OperatorRegistry()
    reg.register(op, enabled=True, priority=10)
    return reg, inv


def _svo_csg(tense: str = "PAST") -> ControlledSemanticGraph:
    csg = ControlledSemanticGraph()
    csg.add_node(CSGNode(id="subj", prime_id="I",
                         attributes={"person": "1", "number": "sg"}))
    csg.add_node(CSGNode(id="pred", prime_id="SEE",
                         attributes={"tense": tense}))
    csg.add_node(CSGNode(id="obj", prime_id="MAN"))
    csg.add_edge(CSGEdge(from_id="subj", to_id="pred", relation="agent"))
    csg.add_edge(CSGEdge(from_id="pred", to_id="obj",  relation="patient"))
    return csg


def _default_typology() -> TypologyMatrix:
    return TypologyMatrix(
        word_order="SVO",
        tense_system="inflectional",
        morph_type="agglutinative",
        case_system="nominative_accusative",
        agreement_features=["person", "number"],
        morpheme_table={"ACC": "o", "PAST": "et", "1SG": "m", "3SG": "s"},
    )


class TestCSGPipelineBasic:
    def setup_method(self):
        self.primes = _prime_graph()
        self.typ = _default_typology()
        self.reg, self.inv = _registry_no_ops()
        self.pipeline = CSGPipeline(self.primes, self.typ, self.reg, self.inv)
        self.hs = _hot_state(
            _entity("I",   "pron.", "ni"),
            _entity("SEE", "v.",    "vid"),
            _entity("MAN", "n.",    "min"),
        )

    def test_generate_returns_result(self):
        csg = _svo_csg()
        result = self.pipeline.generate(csg, self.hs, era=0)
        assert isinstance(result, GenerationResult)

    def test_generate_sentence_non_empty(self):
        csg = _svo_csg()
        result = self.pipeline.generate(csg, self.hs, era=0)
        assert result.sentence.strip() != ""

    def test_generate_era_in_result(self):
        csg = _svo_csg()
        result = self.pipeline.generate(csg, self.hs, era=3)
        assert result.era == 3

    def test_generate_svo_order(self):
        csg = _svo_csg(tense="")
        result = self.pipeline.generate(csg, self.hs, era=0)
        tokens = result.tokens
        ni_idx  = tokens.index("ni")
        vid_idx = next(i for i, t in enumerate(tokens) if t.startswith("vid"))
        min_idx = next(i for i, t in enumerate(tokens) if t.startswith("min"))
        assert ni_idx < vid_idx < min_idx

    def test_generate_object_has_accusative(self):
        csg = _svo_csg(tense="")
        result = self.pipeline.generate(csg, self.hs, era=0)
        assert any(t.endswith("o") for t in result.tokens)

    def test_generate_verb_has_past_suffix(self):
        csg = _svo_csg(tense="PAST")
        result = self.pipeline.generate(csg, self.hs, era=0)
        assert any("et" in t for t in result.tokens)

    def test_generate_lexmap_used_populated(self):
        csg = _svo_csg()
        result = self.pipeline.generate(csg, self.hs, era=0)
        assert "I" in result.lexmap_used
        assert result.lexmap_used["I"] == "ni"

    def test_generate_empty_hot_state_graceful(self):
        csg = _svo_csg()
        result = self.pipeline.generate(csg, EngineHotState(), era=0)
        assert isinstance(result, GenerationResult)


class TestCSGPipelineWithSurfacePhonology:
    def test_final_vowel_drop_applied_to_output(self):
        reg, inv = _registry_with_fvd()
        primes = _prime_graph()
        typ = TypologyMatrix(
            word_order="SVO",
            case_system="none",
            tense_system="tenseless",
            agreement_features=[],
        )
        pipeline = CSGPipeline(primes, typ, reg, inv)
        hs = _hot_state(
            _entity("I",   "pron.", "ni"),
            _entity("SEE", "v.",    "vidi"),
            _entity("MAN", "n.",    "minu"),
        )
        csg = _svo_csg(tense="")
        result = pipeline.generate(csg, hs, era=1)
        assert "vidi" not in result.tokens
        assert "minu" not in result.tokens
        assert "vid" in result.tokens
        assert "min" in result.tokens


class TestCSGPipelineCompareEras:
    def test_compare_eras_sorted_by_era(self):
        primes = _prime_graph()
        reg, inv = _registry_no_ops()

        typ0 = TypologyMatrix(word_order="SOV", case_system="none",
                              tense_system="tenseless", agreement_features=[])
        typ5 = TypologyMatrix(word_order="SVO", case_system="none",
                              tense_system="tenseless", agreement_features=[])

        hs0 = _hot_state(
            _entity("I",   "pron.", "ego"),
            _entity("SEE", "v.",    "vide"),
            _entity("MAN", "n.",    "homo"),
        )
        hs5 = _hot_state(
            _entity("I",   "pron.", "e"),
            _entity("SEE", "v.",    "vi"),
            _entity("MAN", "n.",    "om"),
        )

        pipeline = CSGPipeline(primes, typ0, reg, inv)
        snapshots = {0: (hs0, typ0), 5: (hs5, typ5)}
        csg = _svo_csg(tense="")
        results = pipeline.compare_eras(csg, snapshots)

        assert [r.era for r in results] == [0, 5]

    def test_compare_eras_different_sentences(self):
        primes = _prime_graph()
        reg, inv = _registry_no_ops()

        typ0 = TypologyMatrix(word_order="SOV", case_system="none",
                              tense_system="tenseless", agreement_features=[])
        typ5 = TypologyMatrix(word_order="SVO", case_system="none",
                              tense_system="tenseless", agreement_features=[])

        hs0 = _hot_state(
            _entity("I",   "pron.", "ego"),
            _entity("SEE", "v.",    "vide"),
            _entity("MAN", "n.",    "homo"),
        )
        hs5 = _hot_state(
            _entity("I",   "pron.", "e"),
            _entity("SEE", "v.",    "vi"),
            _entity("MAN", "n.",    "om"),
        )

        pipeline = CSGPipeline(primes, typ0, reg, inv)
        results = pipeline.compare_eras(_svo_csg(tense=""), {0: (hs0, typ0), 5: (hs5, typ5)})

        assert results[0].sentence != results[1].sentence

    def test_compare_eras_word_order_differs(self):
        """Era 0 uses SOV, Era 5 uses SVO — same tokens, different order."""
        primes = _prime_graph()
        reg, inv = _registry_no_ops()

        hs = _hot_state(
            _entity("I",   "pron.", "ni"),
            _entity("SEE", "v.",    "vid"),
            _entity("MAN", "n.",    "min"),
        )
        typ_sov = TypologyMatrix(word_order="SOV", case_system="none",
                                 tense_system="tenseless", agreement_features=[])
        typ_svo = TypologyMatrix(word_order="SVO", case_system="none",
                                 tense_system="tenseless", agreement_features=[])
        pipeline = CSGPipeline(primes, typ_sov, reg, inv)
        results = pipeline.compare_eras(
            _svo_csg(tense=""),
            {0: (hs, typ_sov), 5: (hs, typ_svo)},
        )
        assert results[0].tokens != results[1].tokens

    def test_str_representation(self):
        primes = _prime_graph()
        reg, inv = _registry_no_ops()
        typ = TypologyMatrix(word_order="SVO", case_system="none",
                             tense_system="tenseless", agreement_features=[])
        pipeline = CSGPipeline(primes, typ, reg, inv)
        hs = _hot_state(_entity("I", "pron.", "ni"), _entity("SEE", "v.", "vid"),
                        _entity("MAN", "n.", "min"))
        result = pipeline.generate(_svo_csg(tense=""), hs, era=2)
        assert "[Era 2]" in str(result)
