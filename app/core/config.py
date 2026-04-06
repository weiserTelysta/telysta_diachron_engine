from pathlib import Path


class Configs:
    def __init__(self):
        # 基础目录定位
        self.BASE_DIR = Path(__file__).resolve().parent.parent.parent
        # 数据目录定义
        self.DATA_DIR = self.BASE_DIR / "data"
        self.LEXICOLIST_DIR = self.DATA_DIR / "lexicolist"
        self.SNAPSHOT_DIR = self.DATA_DIR / "era_snapshots"

        # 全局配置
        self.SEED_MAX = (2**64) - 1
        self.SEED_MIN = 0

    def get_lexicon_path(self, filename: str) -> Path:
        """获取词表完整路径"""
        return self.LEXICOLIST_DIR / filename


configs = Configs()
