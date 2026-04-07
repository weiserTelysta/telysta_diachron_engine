"""LLM response security layer.

Sits between ``LLMBackend.call()`` and contract parsing.  Every raw
JSON string from the LLM passes through ``sanitize()`` before being
deserialized into a contract dataclass.

Six defence layers:
  1. JSON parse isolation
  2. Field whitelist enforcement
  3. Type coercion / rejection
  4. Length truncation
  5. Content sanitization (injection markers, IPA charset, prime ID format)
  6. Rate anomaly detection (per-era proposal cap)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<\s*script", re.IGNORECASE),
    re.compile(r"\$\("),
    re.compile(r"`[^`]*`"),
    re.compile(r"<\s*/?\s*(?:iframe|object|embed|form|input)", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
]

_PRIME_ID_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")

_IPA_CHARSET = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ɑɐɒæɓʙβɔɕçɗɖðʤəɘɚɛɜɝɞɟʄɡɠɢʛɦɧħɥʜɨɪʝɭɬɫɮʟɱɯɰŋɳɲɴø"
    "ɵɸθœɶʘɹɺɾɻʀʁɽʂʃʈʧʉʊʋⱱɤʌɣɰʍχʎʏʑʐʒʔʕʢʡ"
    "ːˑˈˌ̩̯̥̤̰̝̞̘̙̻̼̹̜̃̊̄̈̂̌̆"
    "aeiouəɛɪɔʊæøɯɨʉɤɵɐɞ"
    " .ˈˌ"
)


@dataclass
class SanitizeResult:
    ok: bool
    data: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class FieldSpec:
    type: type | str
    max_length: int | None = None
    max_items: int | None = None
    pattern: re.Pattern[str] | None = None
    is_ipa: bool = False


FIELD_SPECS: dict[str, dict[str, FieldSpec]] = {
    "EraLoreResponse": {
        "narrative": FieldSpec(type=str, max_length=500),
        "tags": FieldSpec(type="list[str]", max_items=10, max_length=32),
        "era": FieldSpec(type=int),
    },
    "SemanticProposalResponse": {
        "word_id": FieldSpec(type=str, max_length=64),
        "shift_type": FieldSpec(type=str, max_length=32),
        "from_prime": FieldSpec(type=str, max_length=64, pattern=_PRIME_ID_RE),
        "to_prime": FieldSpec(type=str, max_length=64, pattern=_PRIME_ID_RE),
        "chain": FieldSpec(type="list[str]", max_items=20, max_length=64),
        "confidence": FieldSpec(type=float),
        "reasoning": FieldSpec(type=str, max_length=300),
    },
    "RagLexemeResponse": {
        "new_concept": FieldSpec(type=str, max_length=64),
        "new_ipa": FieldSpec(type=str, max_length=64, is_ipa=True),
        "root_ids_used": FieldSpec(type="list[str]", max_items=10, max_length=64),
        "morpheme_breakdown": FieldSpec(type=str, max_length=128),
        "confidence": FieldSpec(type=float),
        "reasoning": FieldSpec(type=str, max_length=300),
    },
    "ReverseEtymologyResponse": {
        "modern_word_id": FieldSpec(type=str, max_length=64),
        "accepted_chain": FieldSpec(type="list[str]", max_items=20, max_length=64),
        "rejected_candidates": FieldSpec(type="list[str]", max_items=20, max_length=64),
        "confidence_band": FieldSpec(type=str, max_length=16),
        "reasoning": FieldSpec(type=str, max_length=300),
    },
}


def sanitize(
    raw_json: str,
    response_type: str,
    *,
    max_proposals_per_era: int = 5,
    _proposal_counter: dict[int, int] | None = None,
    current_era: int | None = None,
) -> SanitizeResult:
    """Validate and clean a raw LLM JSON response.

    Returns ``SanitizeResult(ok=True, data=...)`` on success, or
    ``SanitizeResult(ok=False, errors=[...])`` on rejection.
    """
    # --- Layer 1: JSON parse isolation ---
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return SanitizeResult(ok=False, errors=[f"JSON parse failed: {exc}"])

    if not isinstance(data, dict):
        return SanitizeResult(ok=False, errors=["Top-level value must be an object"])

    specs = FIELD_SPECS.get(response_type)
    if specs is None:
        return SanitizeResult(ok=False, errors=[f"Unknown response type: {response_type}"])

    errors: list[str] = []

    # --- Layer 2: Field whitelist ---
    allowed_keys = set(specs.keys())
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        logger.warning("Sanitizer: dropping extra fields %s", extra_keys)
        for k in extra_keys:
            del data[k]

    # --- Layer 3 + 4: Type check & length truncation ---
    for fname, fspec in specs.items():
        if fname not in data:
            continue
        val = data[fname]

        if fspec.type == str:
            if not isinstance(val, str):
                errors.append(f"Field '{fname}' expected str, got {type(val).__name__}")
                continue
            if fspec.max_length and len(val) > fspec.max_length:
                logger.warning("Sanitizer: truncating '%s' from %d to %d", fname, len(val), fspec.max_length)
                data[fname] = val[: fspec.max_length]

        elif fspec.type == int:
            if not isinstance(val, int):
                errors.append(f"Field '{fname}' expected int, got {type(val).__name__}")

        elif fspec.type == float:
            if not isinstance(val, (int, float)):
                errors.append(f"Field '{fname}' expected number, got {type(val).__name__}")
            else:
                data[fname] = float(val)

        elif fspec.type == "list[str]":
            if not isinstance(val, list):
                errors.append(f"Field '{fname}' expected list, got {type(val).__name__}")
                continue
            if fspec.max_items and len(val) > fspec.max_items:
                logger.warning("Sanitizer: truncating list '%s' from %d to %d items", fname, len(val), fspec.max_items)
                val = val[: fspec.max_items]
                data[fname] = val
            cleaned: list[str] = []
            for i, item in enumerate(val):
                if not isinstance(item, str):
                    errors.append(f"Field '{fname}[{i}]' expected str, got {type(item).__name__}")
                    continue
                if fspec.max_length and len(item) > fspec.max_length:
                    item = item[: fspec.max_length]
                cleaned.append(item)
            data[fname] = cleaned

    if errors:
        return SanitizeResult(ok=False, errors=errors)

    # --- Layer 5: Content sanitization ---
    for fname, fspec in specs.items():
        if fname not in data:
            continue
        val = data[fname]

        if isinstance(val, str):
            for pat in _INJECTION_PATTERNS:
                if pat.search(val):
                    return SanitizeResult(
                        ok=False,
                        errors=[f"Injection pattern detected in field '{fname}'"],
                    )

            if fspec.pattern and not fspec.pattern.match(val):
                errors.append(f"Field '{fname}' failed pattern check: {val!r}")

            if fspec.is_ipa:
                cleaned_ipa = "".join(ch for ch in val if ch in _IPA_CHARSET)
                if cleaned_ipa != val:
                    logger.warning("Sanitizer: stripped non-IPA chars from '%s'", fname)
                    data[fname] = cleaned_ipa

        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    for pat in _INJECTION_PATTERNS:
                        if pat.search(item):
                            return SanitizeResult(
                                ok=False,
                                errors=[f"Injection pattern in list field '{fname}'"],
                            )

    if errors:
        return SanitizeResult(ok=False, errors=errors)

    # --- Layer 6: Rate anomaly detection ---
    if (
        _proposal_counter is not None
        and current_era is not None
        and response_type == "SemanticProposalResponse"
    ):
        count = _proposal_counter.get(current_era, 0) + 1
        _proposal_counter[current_era] = count
        if count > max_proposals_per_era:
            return SanitizeResult(
                ok=False,
                errors=[f"Proposal rate exceeded: {count} > {max_proposals_per_era} for era {current_era}"],
            )

    return SanitizeResult(ok=True, data=data)
