"""Versioned, path-derived random streams for deterministic legacy runs.

This is the migration baseline implementation.  The future Rust core must
define and version its own compatible contract; callers must not depend on
Python's internal ``random.Random`` state representation.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Final


RNG_TREE_VERSION: Final[str] = "legacy-rng-tree-v1"


def _normalise_segment(segment: object) -> str:
    if isinstance(segment, bool):
        return "true" if segment else "false"
    if isinstance(segment, (str, int)):
        value = str(segment)
    else:
        raise TypeError(
            "RngTree path segments must be strings or integers; "
            f"got {type(segment).__name__}"
        )
    if not value:
        raise ValueError("RngTree path segments cannot be empty")
    return value


@dataclass(frozen=True)
class RngTree:
    """Derive independent deterministic RNG streams from stable paths.

    Derivation uses SHA-256 over a versioned JSON payload.  Each call returns
    a fresh generator at the beginning of that path's stream, so a stream
    should be obtained once per logical operation and passed to its callees.
    """

    root_seed: int
    namespace: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.root_seed, bool) or not isinstance(self.root_seed, int):
            raise TypeError("root_seed must be an integer")
        if self.root_seed < 0 or self.root_seed > (2**64 - 1):
            raise ValueError("root_seed must be within the unsigned 64-bit range")

    def child(self, *segments: object) -> "RngTree":
        path = self.namespace + tuple(_normalise_segment(s) for s in segments)
        return RngTree(root_seed=self.root_seed, namespace=path)

    def seed_for(self, *segments: object) -> int:
        path = self.namespace + tuple(_normalise_segment(s) for s in segments)
        if not path:
            raise ValueError("RngTree requires a non-empty derivation path")
        payload = json.dumps(
            {
                "version": RNG_TREE_VERSION,
                "root_seed": str(self.root_seed),
                "path": list(path),
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")

    def python(self, *segments: object) -> random.Random:
        return random.Random(self.seed_for(*segments))

    def numpy(self, *segments: object):
        """Return a NumPy Generator without making NumPy a core dependency here."""
        import numpy as np

        return np.random.default_rng(self.seed_for(*segments))
