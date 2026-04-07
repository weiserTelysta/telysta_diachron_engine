import json
import random
from dataclasses import asdict

from app.core.config import configs
from app.core.logging import get_logger
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory

logger = get_logger(__name__)


class BasicLexiconGenerator:
    def __init__(
        self,
        seed: int,
        inventory: PhonemeInventory,
        lexicolist_filepath: str,
    ) -> None:
        self.seed = seed
        self.inventory = inventory
        self.lexicolist_filepath = lexicolist_filepath
        self.rng = random.Random(self.seed)

    def _json_get(self, filepath: str) -> list:
        with open(filepath, encoding="UTF-8") as f:
            raw_data = json.load(f)
        if isinstance(raw_data, dict):
            return list(raw_data.values())[0]
        return raw_data

    _SYLLABLE_TEMPLATES: list[str] = ["CV", "CVC", "CVCV", "CCVC"]
    _TIER_WEIGHTS: list[float] = [20.0, 30.0, 35.0, 15.0]

    def _ipa_generate(self) -> str:
        """Generate an IPA form using 4-tier syllable complexity sampling.

        Tiers (position-sensitive):
          CV   — open monosyllable
          CVC  — closed monosyllable; coda sampled from sonorant/nasal pool
          CVCV — open disyllable (previous default)
          CCVC — onset-cluster + closed; WellFormednessValidator repairs illegal clusters
        """
        template = self.rng.choices(self._SYLLABLE_TEMPLATES, weights=self._TIER_WEIGHTS, k=1)[0]
        C = self.inventory.sample_consonant
        V = self.inventory.sample_vowel
        Cc = self.inventory.sample_coda_consonant
        rng = self.rng

        if template == "CV":
            return C(rng).symbol + V(rng).symbol
        if template == "CVC":
            return C(rng).symbol + V(rng).symbol + Cc(rng).symbol
        if template == "CVCV":
            return C(rng).symbol + V(rng).symbol + C(rng).symbol + V(rng).symbol
        # CCVC
        return C(rng).symbol + C(rng).symbol + V(rng).symbol + Cc(rng).symbol

    @staticmethod
    def _infer_stress_pattern(ipa: str, inventory: PhonemeInventory) -> str:
        """Infer default stress pattern from syllable count.

        Monosyllabic  → "mono"
        Disyllabic    → "penultimate" (most common cross-linguistically)
        Trisyllabic+  → "penultimate"
        """
        vowel_symbols = frozenset(p.symbol for p in inventory.vowels)
        # Greedy longest-match tokenization to count syllable nuclei
        tokens = inventory.tokenize(ipa)
        syllable_count = sum(1 for t in tokens if t in vowel_symbols)
        if syllable_count <= 1:
            return "mono"
        return "penultimate"

    _GCZ_WEIGHT: float = 0.45  # Grammar Core Zone: function words
    _LZ_WEIGHT: float = 0.55   # Lexical Zone: content words
    _BETA_GCZ: float = 1.5
    _BETA_LZ: float = 2.5
    _ALPHA: float = 1.0

    @staticmethod
    def _zipf_mandelbrot(freq_rank: int, beta: float, alpha: float = 1.0) -> float:
        return 1.0 / (freq_rank + beta) ** alpha

    def _compute_dual_track_weights(self, items: list[dict]) -> list[float]:
        """
        双轨 Zipf-Mandelbrot 频率模型。
        GCZ: word_class=="function", 总权重 0.45, beta=1.5（高频平台区）
        LZ:  word_class=="content",  总权重 0.55, beta=2.5（长尾幂律区）
        """
        weights = [0.0] * len(items)
        gcz_idx = [i for i, x in enumerate(items) if x.get("word_class") == "function"]
        lz_idx  = [i for i, x in enumerate(items) if x.get("word_class") != "function"]

        for zone_indices, zone_weight, beta in (
            (gcz_idx, self._GCZ_WEIGHT, self._BETA_GCZ),
            (lz_idx,  self._LZ_WEIGHT,  self._BETA_LZ),
        ):
            if not zone_indices:
                continue
            raws = [
                self._zipf_mandelbrot(items[i]["true_freq_rank"], beta, self._ALPHA)
                for i in zone_indices
            ]
            total = sum(raws)
            for i, raw in zip(zone_indices, raws):
                weights[i] = round(zone_weight * raw / total, 6)

        return weights

    def _json_save(self, lexicon_data: list[LexicalEntity], filename: str) -> None:
        configs.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        save_path = configs.SNAPSHOT_DIR / filename
        dict_data = [asdict(item) for item in lexicon_data]
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(dict_data, f, ensure_ascii=False, indent=4)
        logger.info("创世快照已永久保存至: %s", save_path)

    def generate(self) -> list[LexicalEntity]:
        logger.info("引擎启动，当前创世种子: %d", self.seed)
        logger.info("正在读取语义图纸: %s", self.lexicolist_filepath)
        logger.info("使用音素库: %s", self.inventory)

        swadesh_list = self._json_get(self.lexicolist_filepath)
        final_lexicon: list[LexicalEntity] = []

        weights = self._compute_dual_track_weights(swadesh_list)

        for index, item in enumerate(swadesh_list):
            concept_en = item.get("en", item.get("word", "unknown"))
            pos = item.get("pos", "n.")
            word_class = item.get("word_class", "content")
            jid = item.get("id", f"era_0_{index + 1}")
            ipa_sound = self._ipa_generate()
            weight = weights[index]

            stress = self._infer_stress_pattern(ipa_sound, self.inventory)
            word_entity = LexicalEntity(
                id=jid,
                concept=concept_en,
                pos=pos,
                ipa_current=ipa_sound,
                ipa_history=[],
                frequency_weight=weight,
                word_class=word_class,
                is_dead=False,
                ipa_exemplars=[{"form": ipa_sound, "weight": 1.0}],
                stress_pattern=stress,
            )

            final_lexicon.append(word_entity)
            logger.debug("[%s] (%s/%s) -> /%s/ w=%s", concept_en, pos, word_class, ipa_sound, weight)

        snapshot_filename = f"era_0_snapshot_seed_{self.seed}.json"
        self._json_save(final_lexicon, snapshot_filename)

        return final_lexicon
