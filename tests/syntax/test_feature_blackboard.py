from app.domain.syntax.feature_blackboard import FeatureBlackboard


class TestFeatureBlackboardBasic:
    def test_write_and_read(self):
        b = FeatureBlackboard()
        b.write("person", "1")
        assert b.read("person") == "1"

    def test_read_missing_returns_none(self):
        assert FeatureBlackboard().read("gender") is None

    def test_read_or_fallback(self):
        b = FeatureBlackboard()
        assert b.read_or("number", "sg") == "sg"

    def test_read_or_present(self):
        b = FeatureBlackboard()
        b.write("number", "pl")
        assert b.read_or("number", "sg") == "pl"

    def test_overwrite(self):
        b = FeatureBlackboard()
        b.write("person", "1")
        b.write("person", "3")
        assert b.read("person") == "3"


class TestFeatureBlackboardClear:
    def test_clear_removes_all(self):
        b = FeatureBlackboard()
        b.write("person", "1")
        b.write("number", "sg")
        b.clear()
        assert b.read("person") is None
        assert b.read("number") is None

    def test_clear_then_write_works(self):
        b = FeatureBlackboard()
        b.write("person", "2")
        b.clear()
        b.write("person", "3")
        assert b.read("person") == "3"


class TestFeatureBlackboardSnapshot:
    def test_snapshot_is_copy(self):
        b = FeatureBlackboard()
        b.write("person", "1")
        snap = b.snapshot()
        snap["person"] = "99"
        assert b.read("person") == "1"

    def test_snapshot_empty(self):
        assert FeatureBlackboard().snapshot() == {}

    def test_snapshot_contains_all_keys(self):
        b = FeatureBlackboard()
        b.write("a", "x")
        b.write("b", "y")
        snap = b.snapshot()
        assert snap == {"a": "x", "b": "y"}


class TestFeatureBlackboardContains:
    def test_contains_written_key(self):
        b = FeatureBlackboard()
        b.write("tense", "PAST")
        assert "tense" in b

    def test_not_contains_missing(self):
        assert "tense" not in FeatureBlackboard()
