from pathlib import Path

import pytest

from app.domain.lexicon.pathways import (
    GrammaticalizationPathway,
    TypologyOutput,
    load_pathways,
)

_YAML = Path("data/grammaticalization_pathways.yaml")


class TestLoadPathways:
    def test_loads_seven_pathways(self):
        pathways = load_pathways(_YAML)
        assert len(pathways) == 7

    def test_all_instances_correct_type(self):
        for pw in load_pathways(_YAML):
            assert isinstance(pw, GrammaticalizationPathway)

    def test_first_pathway_fields(self):
        # come_to_directional: max_freq_rank=30, min_erosion_stage=2
        pw = load_pathways(_YAML)[0]
        assert pw.id == "come_to_directional"
        assert pw.semantic_prime == "come"
        assert pw.target_function == "locative"
        assert pw.max_true_freq_rank == 30
        assert pw.min_erosion_stage == 2

    def test_typology_output_isolating(self):
        pw = load_pathways(_YAML)[0]
        assert pw.typology_output.isolating == "free_particle"

    def test_typology_output_agglutinative(self):
        pw = load_pathways(_YAML)[0]
        assert pw.typology_output.agglutinative == "suffix"

    def test_typology_output_fusional(self):
        pw = load_pathways(_YAML)[0]
        assert pw.typology_output.fusional == "case_ending"


class TestProductTypeFor:
    def setup_method(self):
        self.pw = load_pathways(_YAML)[0]

    def test_isolating_returns_free_particle(self):
        assert self.pw.product_type_for("isolating") == "free_particle"

    def test_agglutinative_returns_suffix(self):
        assert self.pw.product_type_for("agglutinative") == "suffix"

    def test_fusional_returns_case_ending(self):
        assert self.pw.product_type_for("fusional") == "case_ending"

    def test_unknown_morph_type_falls_back_to_agglutinative(self):
        assert self.pw.product_type_for("unknown") == "suffix"


class TestTriggersFor:
    def setup_method(self):
        # come_to_directional: max_freq_rank=30, min_erosion_stage=2
        self.pw = load_pathways(_YAML)[0]

    def test_both_conditions_met(self):
        assert self.pw.triggers_for(freq_rank=20, erosion_stage=3) is True

    def test_freq_rank_too_high(self):
        assert self.pw.triggers_for(freq_rank=50, erosion_stage=3) is False

    def test_erosion_stage_too_low(self):
        assert self.pw.triggers_for(freq_rank=20, erosion_stage=1) is False

    def test_exactly_at_threshold(self):
        assert self.pw.triggers_for(freq_rank=30, erosion_stage=2) is True
