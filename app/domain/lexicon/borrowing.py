from __future__ import annotations

import uuid
from typing import Literal

from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import Phoneme, PhonemeInventory
from app.domain.storage.event_log import DeltaEvent, DeltaEventType
from app.domain.storage.hot_state import EngineHotState


AdaptationRule = Literal[
    "final_cluster_simplification",       # 词尾辅音丛 → 仅保留最后一个辅音
    "illegal_onset_repair",               # 非法词首辅音丛 → 插入过渡元音
    "vowel_to_inventory",                 # 源元音 → 目标音素库特征距离最近的元音
    "obstruent_voicing_neutralization",   # 词尾障碍音 → 清化
]


class PhonologicalAdaptor:
    """Apply a sequence of named adaptation rules to an IPA token sequence.

    Each rule models a cross-linguistically attested nativization process.
    Rules are applied in the order supplied by the caller.
    """

    def adapt(
        self,
        tokens: list[str],
        source_inv: PhonemeInventory,
        target_inv: PhonemeInventory,
        rules: list[str],
    ) -> list[str]:
        result = list(tokens)
        for rule in rules:
            result = self._apply_rule(rule, result, source_inv, target_inv)
        return result

    # ------------------------------------------------------------------
    # Rule dispatch
    # ------------------------------------------------------------------

    def _apply_rule(
        self,
        rule: str,
        tokens: list[str],
        source_inv: PhonemeInventory,
        target_inv: PhonemeInventory,
    ) -> list[str]:
        if rule == "final_cluster_simplification":
            return self._final_cluster_simplification(tokens, target_inv)
        if rule == "illegal_onset_repair":
            return self._illegal_onset_repair(tokens, target_inv)
        if rule == "vowel_to_inventory":
            return self._vowel_to_inventory(tokens, source_inv, target_inv)
        if rule == "obstruent_voicing_neutralization":
            return self._obstruent_voicing_neutralization(tokens, target_inv)
        return tokens

    # ------------------------------------------------------------------
    # Rule implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _final_cluster_simplification(
        tokens: list[str], target_inv: PhonemeInventory
    ) -> list[str]:
        """Remove all but the last consonant in a word-final consonant cluster."""
        if len(tokens) < 2:
            return tokens

        result = list(tokens)
        # Walk backwards; collect trailing consonant run
        cluster_start = len(result)
        for i in range(len(result) - 1, -1, -1):
            p = target_inv.find_by_symbol(result[i])
            if p and not p.features.get("syllabic"):
                cluster_start = i
            else:
                break

        cluster = result[cluster_start:]
        if len(cluster) > 1:
            # Keep only the last consonant of the cluster
            result = result[:cluster_start] + [cluster[-1]]
        return result

    @staticmethod
    def _illegal_onset_repair(
        tokens: list[str], target_inv: PhonemeInventory
    ) -> list[str]:
        """Insert a default epenthetic vowel after an illegal word-initial consonant.

        Simple heuristic: if the word starts with two or more consonants,
        insert the inventory's first vowel between them.
        """
        if len(tokens) < 2:
            return tokens

        p0 = target_inv.find_by_symbol(tokens[0])
        p1 = target_inv.find_by_symbol(tokens[1])
        if (
            p0 and not p0.features.get("syllabic")
            and p1 and not p1.features.get("syllabic")
        ):
            vowels = target_inv.vowels
            if vowels:
                epenthetic = vowels[0].symbol
                return [tokens[0], epenthetic] + tokens[1:]
        return tokens

    @staticmethod
    def _vowel_to_inventory(
        tokens: list[str],
        source_inv: PhonemeInventory,
        target_inv: PhonemeInventory,
    ) -> list[str]:
        """Map each source vowel to the nearest vowel in the target inventory.

        Proximity is measured by Hamming distance on the shared feature set.
        """
        result: list[str] = []
        for tok in tokens:
            src_phoneme = source_inv.find_by_symbol(tok)
            if src_phoneme is None or not src_phoneme.features.get("syllabic"):
                result.append(tok)
                continue
            nearest = PhonologicalAdaptor._nearest_vowel(src_phoneme, target_inv)
            result.append(nearest.symbol if nearest else tok)
        return result

    @staticmethod
    def _nearest_vowel(
        source: Phoneme, target_inv: PhonemeInventory
    ) -> Phoneme | None:
        candidates = target_inv.vowels
        if not candidates:
            return None
        shared_features = set(source.features.keys())

        def hamming(p: Phoneme) -> int:
            return sum(
                1 for f in shared_features
                if p.features.get(f) != source.features.get(f)
            )

        return min(candidates, key=hamming)

    @staticmethod
    def _obstruent_voicing_neutralization(
        tokens: list[str], target_inv: PhonemeInventory
    ) -> list[str]:
        """Word-final voiced obstruents → voiceless (Auslautverhärtung)."""
        if not tokens:
            return tokens
        result = list(tokens)
        last = result[-1]
        p = target_inv.find_by_symbol(last)
        if p and p.features.get("voiced") and not p.features.get("sonorant"):
            devoiced_features = {**p.features, "voiced": False}
            candidate = target_inv.find_by_features(devoiced_features)
            if candidate:
                result[-1] = candidate.symbol
        return result


class BorrowingInjector:
    """Adapt a source word's IPA into the target language and inject it.

    The resulting LexicalEntity carries:
      source_language    = source language name
      dag_parent_ids     = [source_entity.id]
      era_born           = injection era
      morpheme_type      = "root"
    """

    def __init__(self) -> None:
        self._adaptor = PhonologicalAdaptor()

    def inject(
        self,
        concept: str,
        source_entity: LexicalEntity,
        target_hot_state: EngineHotState,
        source_inv: PhonemeInventory,
        target_inv: PhonemeInventory,
        era: int,
        adaptation_rules: list[str],
        source_language: str = "",
        pos: str | None = None,
    ) -> DeltaEvent:
        """Adapt source IPA and inject into target_hot_state.

        Returns a BORROW_WORD DeltaEvent whose new_entity is the adapted word.
        The caller must call hot_state.apply_delta(event) to materialise the change.
        """
        tokens = source_inv.tokenize(source_entity.ipa_current)
        adapted_tokens = self._adaptor.adapt(tokens, source_inv, target_inv, adaptation_rules)
        adapted_ipa = "".join(adapted_tokens)

        new_id = f"borrow_{concept}_{era}_{uuid.uuid4().hex[:6]}"
        new_entity = LexicalEntity(
            id=new_id,
            concept=concept,
            pos=pos or source_entity.pos,
            ipa_current=adapted_ipa,
            ipa_history=[source_entity.ipa_current],
            frequency_weight=source_entity.frequency_weight * 0.5,
            word_class=source_entity.word_class,
            is_dead=False,
            era_born=era,
            source_language=source_language or source_entity.source_language,
            morpheme_type="root",
            dag_parent_ids=[source_entity.id],
        )

        return DeltaEvent(
            event_type=DeltaEventType.BORROW_WORD,
            era=era,
            word_id=new_id,
            new_entity=new_entity,
            dag_parent_id=source_entity.id,
            source_language=source_language,
            edge_type="borrowing",
        )
