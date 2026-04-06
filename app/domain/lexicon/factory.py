# app/domain/lexicon/factory.py

from app.core.config import configs

from .generator import BasicLexiconGenerator


def create_basic_lexicon_generator(settings) -> BasicLexiconGenerator:
    full_path = configs.get_lexicon_path(settings.default_lexicon_name)

    return BasicLexiconGenerator(
        seed=settings.seed,
        consonants=settings.consonants,
        vowels=settings.vowels,
        lexicolist_filepath=str(full_path),
    )
