from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.domain.syntax.semantic_graph import SemanticGraph

RelationType = Literal[
    "agent", "patient", "theme", "location", "time",
    "manner", "cause", "result", "modifier", "predicate",
]


@dataclass
class CSGNode:
    id: str
    prime_id: str
    label: str = ""
    attributes: dict[str, str] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CSGNode) and self.id == other.id


@dataclass
class CSGEdge:
    from_id: str
    to_id: str
    relation: RelationType
    weight: float = 1.0


class ControlledSemanticGraph:
    """In-memory CSG: nodes are CSGNode, edges carry semantic relation labels.

    Node IDs are arbitrary strings; prime_id must exist in the SemanticGraph
    at validation time (not at construction time, to allow incremental building).
    """

    def __init__(self) -> None:
        self._nodes: dict[str, CSGNode] = {}
        self._edges: list[CSGEdge] = []

    def add_node(self, node: CSGNode) -> None:
        self._nodes[node.id] = node

    def add_edge(self, edge: CSGEdge) -> None:
        self._edges.append(edge)

    def get_node(self, node_id: str) -> CSGNode | None:
        return self._nodes.get(node_id)

    @property
    def nodes(self) -> list[CSGNode]:
        return list(self._nodes.values())

    @property
    def edges(self) -> list[CSGEdge]:
        return list(self._edges)

    def _adjacency(self) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = {nid: [] for nid in self._nodes}
        for e in self._edges:
            if e.from_id in adj:
                adj[e.from_id].append(e.to_id)
        return adj

    def has_cycle(self) -> bool:
        """Iterative DFS on CSG edges."""
        WHITE, GRAY, BLACK = 0, 1, 2
        adj = self._adjacency()
        color: dict[str, int] = {nid: WHITE for nid in self._nodes}

        for start in self._nodes:
            if color[start] != WHITE:
                continue
            stack: list[tuple[str, int]] = [(start, 0)]
            color[start] = GRAY
            while stack:
                node, idx = stack[-1]
                children = adj.get(node, [])
                if idx < len(children):
                    stack[-1] = (node, idx + 1)
                    child = children[idx]
                    if child not in color:
                        continue
                    if color[child] == GRAY:
                        return True
                    if color[child] == WHITE:
                        color[child] = GRAY
                        stack.append((child, 0))
                else:
                    color[node] = BLACK
                    stack.pop()
        return False


class CSGValidator:
    """Validates a ControlledSemanticGraph against a SemanticGraph of primes."""

    def __init__(self, prime_graph: SemanticGraph) -> None:
        self._primes = prime_graph

    def validate(self, csg: ControlledSemanticGraph) -> list[str]:
        """Return a list of error messages; empty list means valid."""
        errors: list[str] = []

        if not csg.nodes:
            errors.append("CSG has no nodes")
            return errors

        for node in csg.nodes:
            if node.prime_id not in self._primes:
                errors.append(
                    f"Node '{node.id}' references unknown prime '{node.prime_id}'"
                )

        node_ids = {n.id for n in csg.nodes}
        for edge in csg.edges:
            if edge.from_id not in node_ids:
                errors.append(f"Edge from unknown node '{edge.from_id}'")
            if edge.to_id not in node_ids:
                errors.append(f"Edge to unknown node '{edge.to_id}'")

        if csg.has_cycle():
            errors.append("CSG contains a cycle")

        return errors
