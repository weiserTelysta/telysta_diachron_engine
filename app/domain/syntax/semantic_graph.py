from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class SemanticPrime:
    id: str
    label_en: str
    category: str
    relations: tuple[str, ...]

    @classmethod
    def from_dict(cls, d: dict) -> "SemanticPrime":
        return cls(
            id=d["id"],
            label_en=d["label_en"],
            category=d["category"],
            relations=tuple(d.get("relations", [])),
        )


class SemanticGraph:
    """Directed graph of semantic primes.

    Edges are the 'relations' declared in each prime (child → parent semantics).
    Cycle detection uses iterative DFS to avoid recursion depth limits.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, SemanticPrime] = {}
        self._edges: dict[str, list[str]] = {}  # id → [related_id, ...]

    def add_prime(self, prime: SemanticPrime) -> None:
        self._nodes[prime.id] = prime
        self._edges[prime.id] = list(prime.relations)

    def get(self, prime_id: str) -> SemanticPrime | None:
        return self._nodes.get(prime_id)

    def __contains__(self, prime_id: str) -> bool:
        return prime_id in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def __iter__(self) -> Iterator[SemanticPrime]:
        return iter(self._nodes.values())

    def neighbors(self, prime_id: str) -> list[str]:
        return self._edges.get(prime_id, [])

    def has_cycle(self) -> bool:
        """Iterative DFS cycle detection (WHITE=0, GRAY=1, BLACK=2)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in self._nodes}

        for start in self._nodes:
            if color[start] != WHITE:
                continue
            stack: list[tuple[str, Iterator[str]]] = [
                (start, iter(self._edges.get(start, [])))
            ]
            color[start] = GRAY
            while stack:
                node, children = stack[-1]
                try:
                    child = next(children)
                    if child not in color:
                        continue
                    if color[child] == GRAY:
                        return True
                    if color[child] == WHITE:
                        color[child] = GRAY
                        stack.append((child, iter(self._edges.get(child, []))))
                except StopIteration:
                    color[node] = BLACK
                    stack.pop()
        return False

    def ancestors(self, prime_id: str) -> set[str]:
        """All nodes reachable from prime_id following relation edges."""
        visited: set[str] = set()
        queue = list(self._edges.get(prime_id, []))
        while queue:
            nid = queue.pop()
            if nid in visited or nid not in self._nodes:
                continue
            visited.add(nid)
            queue.extend(self._edges.get(nid, []))
        return visited

    @classmethod
    def from_json(cls, path: str | Path) -> "SemanticGraph":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        graph = cls()
        for node_dict in data["nodes"]:
            graph.add_prime(SemanticPrime.from_dict(node_dict))
        return graph

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {
                    "id": p.id,
                    "label_en": p.label_en,
                    "category": p.category,
                    "relations": list(p.relations),
                }
                for p in self._nodes.values()
            ]
        }
