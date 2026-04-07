"""Era lore generation — read-only narrative rendering.

Produces a short narrative for each era based on the symbolic state
(delta events, active rules, typology).  The output is persisted to
a sidecar JSON file and never enters ``EngineHotState``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.llm.base import LLMBackend
from app.llm.contracts import EraLoreRequest, EraLoreResponse
from app.llm.sanitizer import SanitizeResult, sanitize
from app.llm.schema import ERA_LORE_RESPONSE_SCHEMA

logger = get_logger(__name__)


def _build_lore_prompt(req: EraLoreRequest) -> str:
    lines = [
        "You are a conlang historian. Based on the following linguistic era summary, "
        "write a short narrative (max 100 words) and assign 1-3 tags.",
        "",
        f"Era: {req.era}",
        f"Active sound-change rules: {', '.join(req.active_rules)}",
        f"Morphological type: {req.morph_type}",
        f"Word order: {req.word_order}",
        f"Alive words: {req.alive_count}, Dead words: {req.dead_count}",
    ]
    if req.representative_changes:
        lines.append("Representative changes:")
        for ch in req.representative_changes[:5]:
            lines.append(f"  {ch.get('word', '?')}: {ch.get('old', '?')} -> {ch.get('new', '?')}")
    if req.branch_info:
        lines.append(f"Branches: {', '.join(req.branch_info)}")

    lines.extend([
        "",
        "Reply ONLY with a JSON object: {\"narrative\": \"...\", \"tags\": [\"...\", ...]}",
    ])
    return "\n".join(lines)


def generate_era_lore(
    backend: LLMBackend,
    req: EraLoreRequest,
) -> EraLoreResponse | None:
    """Call the LLM to produce a lore narrative for one era.

    Returns ``None`` if the response is rejected by the sanitizer.
    """
    prompt = _build_lore_prompt(req)
    result = backend.call(prompt, schema_hint=ERA_LORE_RESPONSE_SCHEMA)

    san: SanitizeResult = sanitize(result.raw_json, "EraLoreResponse")
    if not san.ok:
        logger.warning(
            "Lore rejected (era=%d, stage=schema): %s",
            req.era, "; ".join(san.errors),
        )
        return None

    try:
        resp = EraLoreResponse.from_dict(san.data)  # type: ignore[arg-type]
    except KeyError as exc:
        logger.error("Lore contract deserialization failed: %s", exc)
        return None

    resp.era = req.era
    return resp


class LoreSidecar:
    """Persist lore narratives to per-era JSON files alongside snapshots."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, lore: EraLoreResponse) -> Path:
        path = self.base_dir / f"lore_era_{lore.era:04d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(lore.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("Lore saved: %s", path)
        return path

    def load(self, era: int) -> EraLoreResponse | None:
        path = self.base_dir / f"lore_era_{era:04d}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return EraLoreResponse.from_dict(json.load(f))

    def load_all(self) -> list[EraLoreResponse]:
        results: list[EraLoreResponse] = []
        for p in sorted(self.base_dir.glob("lore_era_*.json")):
            with open(p, encoding="utf-8") as f:
                results.append(EraLoreResponse.from_dict(json.load(f)))
        return results
