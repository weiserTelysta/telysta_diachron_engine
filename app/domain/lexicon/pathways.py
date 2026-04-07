from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

MorphemeProductType = Literal["prefix", "suffix", "free_particle", "stem_alternation", "case_ending"]


@dataclass(frozen=True)
class TypologyOutput:
    isolating: MorphemeProductType
    agglutinative: MorphemeProductType
    fusional: MorphemeProductType


@dataclass(frozen=True)
class GrammaticalizationPathway:
    id: str
    semantic_prime: str
    target_function: str
    typology_output: TypologyOutput
    max_true_freq_rank: int
    min_erosion_stage: int

    def product_type_for(self, morph_type: str) -> MorphemeProductType:
        """Return the morpheme product type for the given typological category."""
        if morph_type == "isolating":
            return self.typology_output.isolating
        if morph_type == "fusional":
            return self.typology_output.fusional
        return self.typology_output.agglutinative

    def product_type_for_state(self, domain_state: int) -> MorphemeProductType:
        """Return product type based on per-domain coupling depth (0/1/2)."""
        if domain_state == 0:
            return self.typology_output.isolating
        if domain_state >= 2:
            return self.typology_output.fusional
        return self.typology_output.agglutinative

    def triggers_for(self, freq_rank: int, erosion_stage: int) -> bool:
        """Return True when both trigger conditions are satisfied."""
        return freq_rank <= self.max_true_freq_rank and erosion_stage >= self.min_erosion_stage


def load_pathways(yaml_path: str | Path) -> list[GrammaticalizationPathway]:
    """Load and parse grammaticalization_pathways.yaml into typed dataclasses."""
    data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    result: list[GrammaticalizationPathway] = []
    for entry in data["pathways"]:
        to = entry["typology_output"]
        trigger = entry["trigger"]
        result.append(
            GrammaticalizationPathway(
                id=entry["id"],
                semantic_prime=entry["semantic_prime"],
                target_function=entry["target_function"],
                typology_output=TypologyOutput(
                    isolating=to["isolating"],
                    agglutinative=to["agglutinative"],
                    fusional=to["fusional"],
                ),
                max_true_freq_rank=trigger["max_true_freq_rank"],
                min_erosion_stage=trigger["min_erosion_stage"],
            )
        )
    return result
