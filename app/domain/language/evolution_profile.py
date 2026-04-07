from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvolutionProfile:
    """Evolutionary bias layer bridging worldview inputs to engine parameters.

    Influences existing mechanisms' weights/thresholds/priorities;
    never directly produces IPA or overrides linguistic rules.

    Fields:
        erosion_position_bias: stress_pattern → rate multiplier applied on top of
            ErosionModel.rate().  Keys match LexicalEntity.stress_pattern values
            ("initial" | "penultimate" | "final" | "").
        operator_rate_overrides: operator name → change_rate multiplier, applied
            before each operator's gate check in BranchLanguage.evolve_one_era().
        gram_density_threshold_scale: scales TypologyDriftEngine's
            gram_density_threshold (< 1 → earlier drift, > 1 → later drift).
        preferred_product_types: ordering hint for grammaticalization product type
            selection (e.g. ["free_particle"] for Sino-Tibetan-style languages).
            Informational for now; used by future grammaticalization pathway routing.
    """

    erosion_position_bias: dict[str, float] = field(default_factory=dict)
    operator_rate_overrides: dict[str, float] = field(default_factory=dict)
    gram_density_threshold_scale: float = 1.0
    preferred_product_types: list[str] = field(default_factory=list)


def neutral_profile() -> EvolutionProfile:
    return EvolutionProfile()


_ENV_POSITION_BIAS: dict[str, dict[str, float]] = {
    "forest":   {"final": 0.8,  "penultimate": 0.9, "initial": 1.0, "": 0.9},
    "tundra":   {"final": 1.4,  "penultimate": 1.1, "initial": 0.8, "": 1.2},
    "desert":   {"final": 1.5,  "penultimate": 1.2, "initial": 0.9, "": 1.3},
    "mountain": {"final": 0.6,  "penultimate": 0.8, "initial": 1.0, "": 0.7},
}
_ENV_GRAM_SCALE: dict[str, float] = {
    "forest":   1.0,
    "tundra":   1.0,
    "desert":   0.8,
    "mountain": 1.3,
}

_RACE_OP_OVERRIDES: dict[str, dict[str, float]] = {
    "elven":    {"final_vowel_drop": 0.5,  "voicing_assimilation": 0.7},
    "orcish":   {"voicing_assimilation": 1.8, "coda_cluster_assimilation": 1.5},
    "dwarvish": {"final_vowel_drop": 0.3,  "mid_vowel_drop": 0.3,
                 "voicing_assimilation": 0.4, "coda_cluster_assimilation": 0.5},
    "human":    {},
}
_RACE_POSITION_BIAS: dict[str, dict[str, float]] = {
    "dwarvish": {"final": 0.5, "penultimate": 0.6, "initial": 0.8, "": 0.5},
}
_RACE_PREFERRED: dict[str, list[str]] = {
    "elven":    ["free_particle"],
    "orcish":   ["suffix"],
    "dwarvish": ["stem_alternation"],
    "human":    [],
}


def from_environment(environment: str) -> EvolutionProfile:
    key = environment.lower()
    return EvolutionProfile(
        erosion_position_bias=dict(_ENV_POSITION_BIAS.get(key, {})),
        gram_density_threshold_scale=_ENV_GRAM_SCALE.get(key, 1.0),
    )


def from_race(race: str) -> EvolutionProfile:
    key = race.lower()
    return EvolutionProfile(
        operator_rate_overrides=dict(_RACE_OP_OVERRIDES.get(key, {})),
        erosion_position_bias=dict(_RACE_POSITION_BIAS.get(key, {})),
        preferred_product_types=list(_RACE_PREFERRED.get(key, [])),
    )


def merge(base: EvolutionProfile, overlay: EvolutionProfile) -> EvolutionProfile:
    """Combine two profiles multiplicatively.

    Each numeric bias is multiplied; preferred_product_types from overlay wins
    when non-empty, otherwise falls back to base.
    """
    merged_pos: dict[str, float] = dict(base.erosion_position_bias)
    for k, v in overlay.erosion_position_bias.items():
        merged_pos[k] = merged_pos.get(k, 1.0) * v

    merged_ops: dict[str, float] = dict(base.operator_rate_overrides)
    for k, v in overlay.operator_rate_overrides.items():
        merged_ops[k] = merged_ops.get(k, 1.0) * v

    return EvolutionProfile(
        erosion_position_bias=merged_pos,
        operator_rate_overrides=merged_ops,
        gram_density_threshold_scale=(
            base.gram_density_threshold_scale * overlay.gram_density_threshold_scale
        ),
        preferred_product_types=(
            overlay.preferred_product_types
            if overlay.preferred_product_types
            else list(base.preferred_product_types)
        ),
    )
