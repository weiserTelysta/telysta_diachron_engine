import os
from pathlib import Path

class Configs:
    # 基础目录定位
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

    # 数据目录定义
    DATA_DIR = BASE_DIR / "data"
    LEXICOLIST_DIR = DATA_DIR / "lexicolist"
    SNAPSHOT_DIR = DATA_DIR / "era_snapshots"

    # 全局配置
    SEED = 1816153515
    DEFAULT_LEXICON = "Swadesh-Yakhontov_35.json"

    # 音素池
    consonants = ["p", "t", "k", "m", "n", "s"]
    vowels = ["a", "i", "u", "e", "o"]

    @classmethod
    def get_lexicon_path(cls, filename: str = None) -> Path:
        """方便快速获取词表完整路径"""
        target = filename or cls.DEFAULT_LEXICON
        return cls.LEXICOLIST_DIR / target
    
configs = Configs()