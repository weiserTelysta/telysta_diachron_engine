from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal


EdgeType = Literal["sound_change", "borrowing", "fossil_prefix", "compound"]


@dataclass
class DAGEdge:
    to_id: str
    era: int
    edge_type: EdgeType

    def to_dict(self) -> dict:
        return {"to_id": self.to_id, "era": self.era, "edge_type": self.edge_type}

    @classmethod
    def from_dict(cls, d: dict) -> "DAGEdge":
        return cls(to_id=d["to_id"], era=d["era"], edge_type=d["edge_type"])


class WordDAG:
    """JSON-backed adjacency-list DAG for etymological lineage.

    Nodes are word IDs (strings). Directed edges flow from ancestor → descendant.
    Initial implementation uses an in-memory dict; Neo4j migration path preserved
    by isolating all graph queries to this class.
    """

    def __init__(self) -> None:
        # parent_id → list of outgoing edges
        self._out: dict[str, list[DAGEdge]] = {}
        # child_id → list of incoming parent IDs (reverse index for ancestor queries)
        self._in: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, word_id: str) -> None:
        self._out.setdefault(word_id, [])
        self._in.setdefault(word_id, [])

    def add_edge(
        self, from_id: str, to_id: str, era: int, edge_type: EdgeType
    ) -> None:
        self.add_node(from_id)
        self.add_node(to_id)
        edge = DAGEdge(to_id=to_id, era=era, edge_type=edge_type)
        if edge not in self._out[from_id]:
            self._out[from_id].append(edge)
        if from_id not in self._in[to_id]:
            self._in[to_id].append(from_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def parents(self, word_id: str) -> list[str]:
        return list(self._in.get(word_id, []))

    def children(self, word_id: str) -> list[DAGEdge]:
        return list(self._out.get(word_id, []))

    def ancestors(self, word_id: str) -> list[str]:
        """BFS upward; excludes word_id itself."""
        visited: set[str] = set()
        queue: deque[str] = deque(self._in.get(word_id, []))
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            queue.extend(self._in.get(node, []))
        return list(visited)

    def descendants(self, word_id: str) -> list[str]:
        """BFS downward; excludes word_id itself."""
        visited: set[str] = set()
        queue: deque[str] = deque(
            e.to_id for e in self._out.get(word_id, [])
        )
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            queue.extend(e.to_id for e in self._out.get(node, []))
        return list(visited)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "nodes": list(self._out.keys()),
            "edges": [
                {"from_id": from_id, **edge.to_dict()}
                for from_id, edges in self._out.items()
                for edge in edges
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WordDAG":
        dag = cls()
        for node_id in d.get("nodes", []):
            dag.add_node(node_id)
        for e in d.get("edges", []):
            dag.add_edge(
                from_id=e["from_id"],
                to_id=e["to_id"],
                era=e["era"],
                edge_type=e["edge_type"],
            )
        return dag

    def __len__(self) -> int:
        return len(self._out)

    def __repr__(self) -> str:
        edge_count = sum(len(v) for v in self._out.values())
        return f"WordDAG(nodes={len(self)}, edges={edge_count})"
