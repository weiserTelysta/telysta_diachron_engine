import pytest

from app.domain.syntax.typology import TypologyMatrix


class TestTypologyMatrixDefaults:
    def test_default_word_order(self):
        m = TypologyMatrix()
        assert m.word_order == "SVO"

    def test_default_tense_system(self):
        assert TypologyMatrix().tense_system == "inflectional"

    def test_default_morph_type(self):
        assert TypologyMatrix().morph_type == "agglutinative"

    def test_default_case_system(self):
        assert TypologyMatrix().case_system == "nominative_accusative"

    def test_default_agreement_features(self):
        m = TypologyMatrix()
        assert "person" in m.agreement_features
        assert "number" in m.agreement_features

    def test_default_morpheme_table_empty(self):
        assert TypologyMatrix().morpheme_table == {}


class TestTypologyMatrixGetters:
    def setup_method(self):
        self.m = TypologyMatrix(
            word_order="SOV",
            morpheme_table={"ACC": "o", "PAST": "et", "PRE:FUT": "ga"},
        )

    def test_get_suffix_present(self):
        assert self.m.get_suffix("ACC") == "o"
        assert self.m.get_suffix("PAST") == "et"

    def test_get_suffix_absent(self):
        assert self.m.get_suffix("NOM") == ""

    def test_get_prefix_present(self):
        assert self.m.get_prefix("FUT") == "ga"

    def test_get_prefix_absent(self):
        assert self.m.get_prefix("NEG") == ""


class TestWordOrderSlots:
    def test_svo_slots(self):
        m = TypologyMatrix(word_order="SVO")
        assert m.subject_order_slot() == 0
        assert m.verb_order_slot() == 1
        assert m.object_order_slot() == 2

    def test_sov_slots(self):
        m = TypologyMatrix(word_order="SOV")
        assert m.subject_order_slot() == 0
        assert m.object_order_slot() == 1
        assert m.verb_order_slot() == 2

    def test_vso_slots(self):
        m = TypologyMatrix(word_order="VSO")
        assert m.verb_order_slot() == 0
        assert m.subject_order_slot() == 1
        assert m.object_order_slot() == 2


class TestInvalidWordOrder:
    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            TypologyMatrix(word_order="XYZ")  # type: ignore[arg-type]


class TestCloneWith:
    def test_clone_changes_word_order(self):
        m = TypologyMatrix(word_order="SVO")
        m2 = m.clone_with(word_order="SOV")
        assert m2.word_order == "SOV"
        assert m.word_order == "SVO"

    def test_clone_preserves_morpheme_table(self):
        m = TypologyMatrix(morpheme_table={"ACC": "o"})
        m2 = m.clone_with(word_order="SOV")
        assert m2.morpheme_table == {"ACC": "o"}

    def test_clone_invalid_raises(self):
        m = TypologyMatrix()
        with pytest.raises(ValueError):
            m.clone_with(word_order="BAD")  # type: ignore[arg-type]
