from dataclasses import dataclass, field
from typing import List


@dataclass
class SemanticEraEntry:
    """One auditable record of an LLM-proposed semantic change."""
    era: int
    proposal_type: str          # "metaphor" | "metonymy" | "broadening" | "narrowing" | "lore_only"
    from_prime: str = ""
    to_prime: str = ""
    chain: List[str] = field(default_factory=list)
    validator_status: str = ""  # "accepted" | "rejected" | "lore_only"
    reason: str = ""
    lore_only: bool = False


@dataclass
class LexicalEntity:
    # --- Phase 0 ---
    id: str
    concept: str
    pos: str
    ipa_current: str
    ipa_history: List[str]
    frequency_weight: float
    word_class: str = "content"  # "content" | "function"
    is_dead: bool = False

    # --- Phase 1 ---
    ipa_exemplars: List[dict] = field(default_factory=list)
    # [{"form": "/taka/", "weight": 0.7}, {"form": "/taga/", "weight": 0.3}]
    stress_pattern: str = ""

    # --- Phase 2 ---
    era_born: int = 0
    source_language: str = ""
    morpheme_type: str = "root"
    dag_parent_ids: List[str] = field(default_factory=list)
    scar_log: List[str] = field(default_factory=list)

    # --- Phase 3 ---
    semantic_primes: List[str] = field(default_factory=list)
    semantic_era_log: List[SemanticEraEntry] = field(default_factory=list)

    # --- Phase 4 ---
    grammaticalization_stage: int = 0
    # 0=实词, 1=附着词(clitic), 2=词缀(affix), 3=消失(disappeared)
    grammaticalized_from_id: str = ""
    grammatical_function: str = ""
    # "" | "aspect_marker" | "tense_marker" | "case_marker" | "coordinator" | "subordinator" | "locative" | "negation"
    stasis_counter: int = 0

    _GRAM_STAGE_MAX: int = 3

    def __post_init__(self) -> None:
        if self.grammaticalization_stage > self._GRAM_STAGE_MAX:
            self.grammaticalization_stage = self._GRAM_STAGE_MAX
