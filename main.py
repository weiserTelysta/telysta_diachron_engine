"""TelystaLexisEngine — CLI entry point.

All business logic lives in ``app/engine/``.  This file is a thin
wrapper: create session → run → print summary → demo.
"""

from app.core.logging import get_logger
from app.engine.demo import run_cli_demo
from app.engine.session import EngineSession

logger = get_logger(__name__)


def main() -> None:
    session = EngineSession(seed=888, is_llm=True, era_steps=100)
    result = session.run()

    logger.info(
        "创世 %d 词 → 演化 %d 时代 → 最终 %s / %s",
        len(result.generated_words),
        result.era_steps,
        result.final_typology.morph_type,
        result.final_typology.word_order,
    )

    run_cli_demo(result)


if __name__ == "__main__":
    main()
