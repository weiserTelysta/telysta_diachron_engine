"""Canonical read model and semantic hashes for the legacy Python engine.

The schema deliberately describes observable legacy state.  It is a migration
adapter, not the final Rust ``LanguageState`` contract.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, deque
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Iterable, Mapping, Sequence

if TYPE_CHECKING:
    from app.domain.phonology.phoneme import PhonemeInventory
    from app.domain.phonology.validator import WellFormednessValidator
    from app.domain.storage.event_log import DeltaEvent
    from app.domain.storage.hot_state import EngineHotState
    from app.domain.syntax.typology import TypologyMatrix


LEGACY_CANONICAL_SCHEMA: Final[str] = "telysta.legacy-state.v1"
SEMANTIC_HASH_ALGORITHM: Final[str] = "sha256"
_NON_SEMANTIC_EVENT_FIELDS: Final[frozenset[str]] = frozenset({"timestamp"})


def canonical_id(value: object, *, namespace: str = "entity") -> str:
    """Normalise a legacy ID without silently accepting ambiguous values."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{namespace} ID must be a non-empty string or integer")
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str):
        raise TypeError(f"{namespace} ID must be a string or integer")
    result = value.strip()
    if not result:
        raise ValueError(f"{namespace} ID cannot be empty")
    return result


def _normalise(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, Enum):
        return _normalise(value.value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        items: list[tuple[str, Any]] = []
        seen_keys: set[str] = set()
        for key, item in value.items():
            key_string = canonical_id(key, namespace="mapping key")
            if key_string in seen_keys:
                raise ValueError(f"Duplicate canonical mapping key: {key_string!r}")
            seen_keys.add(key_string)
            items.append((key_string, _normalise(item)))
        return {key: item for key, item in sorted(items, key=lambda pair: pair[0])}
    if isinstance(value, (set, frozenset)):
        normalised = [_normalise(item) for item in value]
        return sorted(normalised, key=_canonical_sort_key)
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Canonical semantic state cannot contain NaN or infinity")
        return 0.0 if value == 0.0 else value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"Unsupported canonical value: {type(value).__name__}")


def _canonical_sort_key(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _normalise(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_lexicon(hot: "EngineHotState") -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_key, entity in hot.lexicon.items():
        key = canonical_id(raw_key, namespace="lexicon key")
        entity_id = canonical_id(entity.id, namespace="lexeme")
        if key != entity_id:
            raise ValueError(f"Lexicon key {key!r} does not match entity ID {entity_id!r}")
        if entity_id in seen:
            raise ValueError(f"Duplicate canonical lexeme ID: {entity_id!r}")
        seen.add(entity_id)
        raw = {
            field: value
            for field, value in asdict(entity).items()
            if not field.startswith("_")
        }
        raw["id"] = entity_id
        raw["dag_parent_ids"] = sorted(
            canonical_id(parent, namespace="DAG parent")
            for parent in raw.get("dag_parent_ids", [])
        )
        entries.append(_normalise(raw))
    return sorted(entries, key=lambda entry: entry["id"])


def _canonical_dag(hot: "EngineHotState") -> dict[str, Any]:
    raw = hot.dag.to_dict()
    nodes = sorted(canonical_id(node, namespace="DAG node") for node in raw.get("nodes", []))
    if len(nodes) != len(set(nodes)):
        raise ValueError("DAG contains duplicate canonical node IDs")
    edges = [
        {
            "from_id": canonical_id(edge["from_id"], namespace="DAG source"),
            "to_id": canonical_id(edge["to_id"], namespace="DAG target"),
            "era": int(edge["era"]),
            "edge_type": str(edge["edge_type"]),
        }
        for edge in raw.get("edges", [])
    ]
    edges.sort(key=lambda edge: (edge["from_id"], edge["to_id"], edge["era"], edge["edge_type"]))
    return {"nodes": nodes, "edges": edges}


def _event_dict(event: "DeltaEvent | Mapping[str, Any]") -> dict[str, Any]:
    if isinstance(event, Mapping):
        raw = dict(event)
    elif is_dataclass(event):
        raw = asdict(event)
    else:
        raise TypeError(f"Unsupported event value: {type(event).__name__}")
    for field in _NON_SEMANTIC_EVENT_FIELDS:
        raw.pop(field, None)
    if raw.get("word_id"):
        raw["word_id"] = canonical_id(raw["word_id"], namespace="event word")
    if raw.get("dag_parent_id"):
        raw["dag_parent_id"] = canonical_id(raw["dag_parent_id"], namespace="event parent")
    return _normalise(raw)


def canonical_legacy_state(
    hot: "EngineHotState",
    typology: "TypologyMatrix | None" = None,
    events: Sequence["DeltaEvent | Mapping[str, Any]"] = (),
) -> dict[str, Any]:
    return {
        "schema": LEGACY_CANONICAL_SCHEMA,
        "state": {
            "era": int(hot.current_era),
            "swadesh_concepts": sorted(str(item) for item in hot.swadesh_concepts),
        },
        "lexicon": _canonical_lexicon(hot),
        "dag": _canonical_dag(hot),
        "typology": _normalise(typology.to_dict()) if typology is not None else None,
        "events": [_event_dict(event) for event in events],
    }


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def semantic_hashes(canonical_state: Mapping[str, Any]) -> dict[str, Any]:
    if canonical_state.get("schema") != LEGACY_CANONICAL_SCHEMA:
        raise ValueError(f"Unsupported canonical schema: {canonical_state.get('schema')!r}")
    domains = {
        "lexicon": _sha256(canonical_state.get("lexicon", [])),
        "dag": _sha256(canonical_state.get("dag", {})),
        "typology": _sha256(canonical_state.get("typology")),
        "events": _sha256(canonical_state.get("events", [])),
    }
    return {
        "schema": LEGACY_CANONICAL_SCHEMA,
        "algorithm": SEMANTIC_HASH_ALGORITHM,
        "domains": domains,
        "full": _sha256(canonical_state),
    }


def _connected_components(nodes: Iterable[str], edges: Sequence[Mapping[str, Any]]) -> int:
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    for edge in edges:
        source = str(edge["from_id"])
        target = str(edge["to_id"])
        adjacency.setdefault(source, set()).add(target)
        adjacency.setdefault(target, set()).add(source)
    components = 0
    remaining = set(adjacency)
    while remaining:
        components += 1
        queue = deque([remaining.pop()])
        while queue:
            current = queue.popleft()
            for neighbour in adjacency[current] & remaining:
                remaining.remove(neighbour)
                queue.append(neighbour)
    return components


@dataclass(frozen=True)
class BaselineReport:
    schema: str
    hashes: dict[str, Any]
    counts: dict[str, int]
    distributions: dict[str, dict[str, int]]
    phonology: dict[str, float | int]
    graph: dict[str, int]
    rule_applications: dict[str, int]
    hard_errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return _normalise(asdict(self))


def build_baseline_report(
    hot: "EngineHotState",
    typology: "TypologyMatrix | None" = None,
    events: Sequence["DeltaEvent | Mapping[str, Any]"] = (),
    *,
    inventory: "PhonemeInventory | None" = None,
    validator: "WellFormednessValidator | None" = None,
) -> BaselineReport:
    canonical = canonical_legacy_state(hot, typology, events)
    lexicon = canonical["lexicon"]
    alive = [entry for entry in lexicon if not entry["is_dead"]]
    forms = [entry["ipa_current"] for entry in alive]
    pos = Counter(str(entry["pos"]) for entry in alive)
    word_classes = Counter(str(entry["word_class"]) for entry in alive)
    rules = Counter(
        str(event.get("rule_name"))
        for event in canonical["events"]
        if event.get("rule_name")
    )

    segments = 0
    syllables = 0
    illegal_forms = 0
    unknown_segments = 0
    vowel_symbols: set[str] = set()
    known_symbols: set[str] = set()
    if inventory is not None:
        vowel_symbols = {phoneme.symbol for phoneme in inventory.vowels}
        known_symbols = {phoneme.symbol for phoneme in inventory.phonemes}
        for form in forms:
            tokens = inventory.tokenize(form)
            segments += len(tokens)
            syllables += sum(token in vowel_symbols for token in tokens)
            unknown_segments += sum(token not in known_symbols for token in tokens)
            if validator is not None and not validator.is_legal(tokens):
                illegal_forms += 1

    dag = canonical["dag"]
    node_set = set(dag["nodes"])
    errors: list[str] = []
    for edge in dag["edges"]:
        if edge["from_id"] not in node_set or edge["to_id"] not in node_set:
            errors.append(f"dangling DAG edge: {edge['from_id']}->{edge['to_id']}")
    if unknown_segments:
        errors.append(f"unknown phoneme tokens: {unknown_segments}")
    if illegal_forms:
        errors.append(f"phonotactically illegal alive forms: {illegal_forms}")

    alive_count = len(alive)
    return BaselineReport(
        schema=LEGACY_CANONICAL_SCHEMA,
        hashes=semantic_hashes(canonical),
        counts={
            "total_words": len(lexicon),
            "alive_words": alive_count,
            "dead_words": len(lexicon) - alive_count,
            "grammaticalized_words": sum(
                int(entry["grammaticalization_stage"] > 0) for entry in alive
            ),
            "morphemes": len(typology.morpheme_table) if typology is not None else 0,
            "events": len(canonical["events"]),
        },
        distributions={
            "part_of_speech": dict(sorted(pos.items())),
            "word_class": dict(sorted(word_classes.items())),
        },
        phonology={
            "average_segments": round(segments / alive_count, 6) if alive_count else 0.0,
            "average_syllables": round(syllables / alive_count, 6) if alive_count else 0.0,
            "homophone_excess": alive_count - len(set(forms)),
            "illegal_forms": illegal_forms,
            "unknown_segments": unknown_segments,
        },
        graph={
            "nodes": len(dag["nodes"]),
            "edges": len(dag["edges"]),
            "connected_components": _connected_components(dag["nodes"], dag["edges"]),
        },
        rule_applications=dict(sorted(rules.items())),
        hard_errors=tuple(errors),
    )
