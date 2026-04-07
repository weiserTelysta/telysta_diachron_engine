"""BiasProfile — style preference isolation layer.

The BiasProfile is the *only* channel through which user-facing presets
(e.g. "Imperial", "Primal", "Modern") influence the morphological state
machine.  It outputs probability *weights*, never direct state assignments.

This prevents the "Style Layer Override" bug where a preset could bypass
the morphological pipeline and directly dictate structural rules.

Usage::

    profile = BiasProfile.imperial()
    # pass to EpochManager or TypologyDriftEngine as transition weight modifiers
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BiasProfile:
    """Probability biases for per-domain state transitions.

    Each domain_*_weights maps ``(from_state, to_state)`` → weight multiplier.
    A weight of 1.0 is neutral; >1 increases transition probability; <1 decreases.
    Missing entries default to 1.0.
    """

    verb_tam_weights: dict[tuple[int, int], float] = field(default_factory=dict)
    verb_agreement_weights: dict[tuple[int, int], float] = field(default_factory=dict)
    noun_case_weights: dict[tuple[int, int], float] = field(default_factory=dict)
    noun_definiteness_weights: dict[tuple[int, int], float] = field(default_factory=dict)

    word_order_rigidity: float = 0.5
    retention_index: float = 0.5
    phonology_bias: dict[str, float] = field(default_factory=dict)

    def weight_for(self, domain: str, from_state: int, to_state: int) -> float:
        """Look up the transition weight for a domain. Returns 1.0 if unset."""
        mapping = getattr(self, f"{domain}_weights", {})
        return mapping.get((from_state, to_state), 1.0)

    @classmethod
    def neutral(cls) -> "BiasProfile":
        return cls()

    @classmethod
    def imperial(cls) -> "BiasProfile":
        """Preset: Imperial/Majestic — favors fusional, rigid word order, high retention."""
        return cls(
            verb_tam_weights={(0, 1): 1.5, (1, 2): 2.0, (2, 0): 0.3},
            verb_agreement_weights={(0, 1): 1.5, (1, 2): 1.8, (2, 0): 0.3},
            noun_case_weights={(0, 1): 2.0, (1, 2): 2.5, (2, 0): 0.2},
            noun_definiteness_weights={(0, 1): 1.2},
            word_order_rigidity=0.8,
            retention_index=0.9,
        )

    @classmethod
    def primal(cls) -> "BiasProfile":
        """Preset: Primal/Guttural — favors agglutinative, simplified TAM."""
        return cls(
            verb_tam_weights={(0, 1): 2.0, (1, 2): 0.5, (2, 0): 1.0},
            verb_agreement_weights={(0, 1): 1.0, (1, 2): 0.3},
            noun_case_weights={(0, 1): 1.5, (1, 2): 0.5},
            word_order_rigidity=0.3,
            retention_index=0.3,
        )

    @classmethod
    def modern(cls) -> "BiasProfile":
        """Preset: Modern/Flexible — favors analytic, strict word order."""
        return cls(
            verb_tam_weights={(0, 1): 0.5, (1, 0): 2.0, (2, 0): 2.5},
            verb_agreement_weights={(0, 1): 0.3, (1, 0): 2.0, (2, 0): 2.5},
            noun_case_weights={(0, 1): 0.3, (1, 0): 2.5, (2, 0): 3.0},
            word_order_rigidity=0.9,
            retention_index=0.2,
        )
