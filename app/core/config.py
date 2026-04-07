from pathlib import Path


class Configs:
    def __init__(self) -> None:
        self.BASE_DIR = Path(__file__).resolve().parent.parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.LEXICOLIST_DIR = self.DATA_DIR / "lexicolist"
        self.SNAPSHOT_DIR = self.DATA_DIR / "era_snapshots"
        self.PHONEME_PRESETS_DIR = self.DATA_DIR / "phoneme_presets"
        self.SOUND_RULES_DIR = self.DATA_DIR / "sound_change_rules"
        self.EPOCH_PRESETS_DIR = self.DATA_DIR / "epoch_presets"
        self.DOMAIN_VOCAB_DIR = self.DATA_DIR / "domain_vocabulary"
        self.LOG_DIR = self.BASE_DIR / "logs"

        self.SEED_MAX = (2**64) - 1
        self.SEED_MIN = 0

    def get_lexicon_path(self, filename: str) -> Path:
        return self.LEXICOLIST_DIR / filename

    def get_phoneme_preset_path(self, preset_name: str) -> Path:
        return self.PHONEME_PRESETS_DIR / f"{preset_name}.json"

    def get_sound_rules_path(self, filename: str) -> Path:
        return self.SOUND_RULES_DIR / filename


configs = Configs()
