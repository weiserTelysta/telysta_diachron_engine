from dataclasses import dataclass
from typing import List


@dataclass
class LexicalEntity:
    id: str
    concept: str
    pos: str
    ipa_current: str
    ipa_history: List[str]
    frequency_weight: float
    is_dead: bool = False
