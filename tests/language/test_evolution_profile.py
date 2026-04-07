import pytest

from app.domain.language.evolution_profile import (
    EvolutionProfile,
    from_environment,
    from_race,
    merge,
    neutral_profile,
)


class TestNeutralProfile:
    def test_all_defaults_are_empty_or_one(self):
        p = neutral_profile()
        assert p.erosion_position_bias == {}
        assert p.operator_rate_overrides == {}
        assert p.gram_density_threshold_scale == pytest.approx(1.0)
        assert p.preferred_product_types == []


class TestFromEnvironment:
    @pytest.mark.parametrize("env", ["forest", "tundra", "desert", "mountain"])
    def test_known_environments_return_non_empty_bias(self, env: str):
        p = from_environment(env)
        assert len(p.erosion_position_bias) > 0

    def test_forest_reduces_final_erosion(self):
        p = from_environment("forest")
        assert p.erosion_position_bias["final"] < 1.0

    def test_desert_amplifies_final_erosion(self):
        p = from_environment("desert")
        assert p.erosion_position_bias["final"] > 1.0

    def test_desert_lowers_gram_drift_threshold(self):
        p = from_environment("desert")
        assert p.gram_density_threshold_scale < 1.0

    def test_mountain_raises_gram_drift_threshold(self):
        p = from_environment("mountain")
        assert p.gram_density_threshold_scale > 1.0

    def test_tundra_amplifies_final_and_suppresses_initial(self):
        p = from_environment("tundra")
        assert p.erosion_position_bias["final"] > 1.0
        assert p.erosion_position_bias["initial"] < 1.0

    def test_unknown_environment_returns_neutral_biases(self):
        p = from_environment("void")
        assert p.erosion_position_bias == {}
        assert p.gram_density_threshold_scale == pytest.approx(1.0)

    def test_case_insensitive(self):
        assert from_environment("Forest").erosion_position_bias == from_environment("forest").erosion_position_bias


class TestFromRace:
    @pytest.mark.parametrize("race", ["elven", "orcish", "dwarvish"])
    def test_known_races_return_operator_overrides(self, race: str):
        p = from_race(race)
        assert len(p.operator_rate_overrides) > 0

    def test_elven_prefers_free_particle(self):
        p = from_race("elven")
        assert "free_particle" in p.preferred_product_types

    def test_elven_slows_final_vowel_drop(self):
        p = from_race("elven")
        assert p.operator_rate_overrides["final_vowel_drop"] < 1.0

    def test_orcish_accelerates_voicing(self):
        p = from_race("orcish")
        assert p.operator_rate_overrides["voicing_assimilation"] > 1.0

    def test_orcish_prefers_suffix(self):
        p = from_race("orcish")
        assert "suffix" in p.preferred_product_types

    def test_dwarvish_suppresses_all_major_operators(self):
        p = from_race("dwarvish")
        for rate in p.operator_rate_overrides.values():
            assert rate < 1.0

    def test_dwarvish_has_position_bias(self):
        p = from_race("dwarvish")
        assert p.erosion_position_bias.get("final", 1.0) < 1.0

    def test_human_returns_empty_overrides(self):
        p = from_race("human")
        assert p.operator_rate_overrides == {}

    def test_unknown_race_returns_neutral(self):
        p = from_race("goblin")
        assert p.operator_rate_overrides == {}
        assert p.preferred_product_types == []

    def test_case_insensitive(self):
        assert from_race("Elven").preferred_product_types == from_race("elven").preferred_product_types


class TestMerge:
    def test_position_bias_multiplied(self):
        base = EvolutionProfile(erosion_position_bias={"final": 2.0})
        overlay = EvolutionProfile(erosion_position_bias={"final": 0.5})
        merged = merge(base, overlay)
        assert merged.erosion_position_bias["final"] == pytest.approx(1.0)

    def test_new_key_in_overlay_added(self):
        base = EvolutionProfile(erosion_position_bias={"final": 1.5})
        overlay = EvolutionProfile(erosion_position_bias={"initial": 0.8})
        merged = merge(base, overlay)
        assert merged.erosion_position_bias["final"] == pytest.approx(1.5)
        assert merged.erosion_position_bias["initial"] == pytest.approx(0.8)

    def test_operator_overrides_multiplied(self):
        base = EvolutionProfile(operator_rate_overrides={"final_vowel_drop": 2.0})
        overlay = EvolutionProfile(operator_rate_overrides={"final_vowel_drop": 0.5})
        merged = merge(base, overlay)
        assert merged.operator_rate_overrides["final_vowel_drop"] == pytest.approx(1.0)

    def test_gram_scale_multiplied(self):
        base = EvolutionProfile(gram_density_threshold_scale=1.2)
        overlay = EvolutionProfile(gram_density_threshold_scale=0.8)
        merged = merge(base, overlay)
        assert merged.gram_density_threshold_scale == pytest.approx(0.96)

    def test_preferred_types_from_overlay_wins(self):
        base = EvolutionProfile(preferred_product_types=["suffix"])
        overlay = EvolutionProfile(preferred_product_types=["free_particle"])
        merged = merge(base, overlay)
        assert merged.preferred_product_types == ["free_particle"]

    def test_preferred_types_falls_back_to_base_when_overlay_empty(self):
        base = EvolutionProfile(preferred_product_types=["suffix"])
        overlay = EvolutionProfile()
        merged = merge(base, overlay)
        assert merged.preferred_product_types == ["suffix"]

    def test_merge_does_not_mutate_inputs(self):
        base = EvolutionProfile(erosion_position_bias={"final": 1.5})
        overlay = EvolutionProfile(erosion_position_bias={"final": 2.0})
        _ = merge(base, overlay)
        assert base.erosion_position_bias["final"] == pytest.approx(1.5)
        assert overlay.erosion_position_bias["final"] == pytest.approx(2.0)

    def test_environment_plus_race_merge(self):
        env_p = from_environment("desert")
        race_p = from_race("orcish")
        combined = merge(env_p, race_p)
        assert combined.erosion_position_bias.get("final", 1.0) > 1.0
        assert combined.operator_rate_overrides.get("voicing_assimilation", 1.0) > 1.0
