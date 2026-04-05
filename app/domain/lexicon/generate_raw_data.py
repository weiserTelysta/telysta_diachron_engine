import json
import random
from typing import List
from app.domain.lexicon.models import LexicalEntity
from app.core.config import configs

class LexisGenerator:
    def __init__(self, seed: int = None):
        self.seed = seed or configs.SEED
        random.seed(self.seed)

        self.consonants = configs.consonants
        self.vowels = configs.vowels

    def _generate_ipa(self, pos:str) -> str:
        """根据音节结构生成初代 IPA (例如 CV 或 CVC)"""
        c1 = random.choice(self.consonants)
        v1 = random.choice(self.vowels)
        c2 = random.choice(self.consonants)

        if pos.upper() == "NOUN":
            c2 = random.choice(self.consonants)
            return f"{c1}{v1}{c2}"
        return f"{c1}{v1}"
    
    def create_lexico_list(self, file_path:Path) ->List[LexicalEntity]:
        with open(file_path,'r',encoding= 'utf-8') as f:
            raw_data = json.load

        entities = []
        for item in raw_data:
            # 假设 JSON 格式：{"id": "s1", "concept": "water", "pos": "NOUN"}
            ipa = self._generate_ipa(item['pos'])
            
            entity = LexicalEntity(
                id=item['id'],
                concept=item['concept'],
                pos=item['pos'],
                ipa_current=ipa,
                ipa_history=[ipa],  # 初始历史记录就是它自己
                frequency_weight=random.uniform(0.1, 1.0) # 模拟齐夫频率初步分布
            )
            entities.append(entity)
        return entities
    
def run_generation():
    generator = LexisGenerator(seed=42)
    # 指向你的 Swadesh-100.json
    entities = generator.from_swadesh_json("data/lexicolist/swadesh_100.json")

    # 打印或保存到 data/era_snapshots/era_0.json
    print(f"Generated {len(entities)} initial lexical entities for Era 0.")