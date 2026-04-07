from app.core.config import configs
from app.domain.lexicon.generator import BasicLexiconGenerator


def create_basic_lexicon_generator(settings) -> BasicLexiconGenerator:
    full_path = configs.get_lexicon_path(settings.default_lexicon_name)
    return BasicLexiconGenerator(
        seed=settings.seed,
        inventory=settings.inventory,
        lexicolist_filepath=str(full_path),
    )
