from dataclasses import dataclass, field
from typing import List


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
    semantic_era_log: List[dict] = field(default_factory=list)
    # [{"era": 3, "shift": "METAPHOR", "from": "SUN", "to": "SOUL"}]

    # --- Phase 4 ---
    grammaticalization_stage: int = 0
    # 0=实词, 1=原虚词(proto-function), 2=虚词, 3=附着词(clitic), 4=词缀
    grammaticalized_from_id: str = ""
    grammatical_function: str = ""
    # "" | "aspect_marker" | "tense_marker" | "case_marker" | "coordinator" | "subordinator" | "locative" | "negation"
