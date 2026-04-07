from __future__ import annotations

import re

from app.domain.phonology.backends.base import Backend
from app.domain.phonology.ir import SoundChangeRule


class RegexBackend(Backend):
    """List-iteration backend with regex helper utilities.

    The internal apply logic uses the same list-scan algorithm as NativeBackend,
    which guarantees correct IR semantics (no lookbehind issues, no catastrophic
    backtracking). _make_group() is retained as the building block for a future
    true regex implementation (Phase 2+, once rule count exceeds ~30).
    """

    def apply(self, rule: SoundChangeRule, sequence: list[str]) -> list[str]:
        if not sequence:
            return []

        before_syms = rule.env_before_symbols
        after_syms = rule.env_after_symbols
        word_initial = rule.env_flags.get("word_initial", False)
        word_final = rule.env_flags.get("word_final", False)

        if rule.op == "delete":
            return self._apply_delete(sequence, rule, before_syms, after_syms, word_initial, word_final)
        if rule.op == "change":
            return self._apply_change(sequence, rule, before_syms, after_syms, word_initial, word_final)
        if rule.op == "insert":
            return list(sequence)
        return list(sequence)

    def _apply_change(
        self,
        parts: list[str],
        rule: SoundChangeRule,
        before_syms: frozenset[str] | None,
        after_syms: frozenset[str] | None,
        word_initial: bool,
        word_final: bool,
    ) -> list[str]:
        result = list(parts)
        n = len(parts)

        for i, sym in enumerate(parts):
            if sym not in rule.target_symbols:
                continue
            if word_initial and i != 0:
                continue
            if word_final and i != n - 1:
                continue
            prev_sym = parts[i - 1] if i > 0 else None
            next_sym = parts[i + 1] if i < n - 1 else None
            if before_syms is not None and (prev_sym is None or prev_sym not in before_syms):
                continue
            if after_syms is not None and (next_sym is None or next_sym not in after_syms):
                continue
            result[i] = rule.output_map.get(sym, sym)

        return result

    def _apply_delete(
        self,
        parts: list[str],
        rule: SoundChangeRule,
        before_syms: frozenset[str] | None,
        after_syms: frozenset[str] | None,
        word_initial: bool,
        word_final: bool,
    ) -> list[str]:
        result: list[str] = []
        n = len(parts)

        for i, sym in enumerate(parts):
            if sym not in rule.target_symbols:
                result.append(sym)
                continue
            if word_initial and i != 0:
                result.append(sym)
                continue
            if word_final and i != n - 1:
                result.append(sym)
                continue
            prev_sym = parts[i - 1] if i > 0 else None
            next_sym = parts[i + 1] if i < n - 1 else None
            if before_syms is not None and (prev_sym is None or prev_sym not in before_syms):
                result.append(sym)
                continue
            if after_syms is not None and (next_sym is None or next_sym not in after_syms):
                result.append(sym)
                continue

        return result

    @staticmethod
    def _make_group(symbols: frozenset[str]) -> str:
        """Build a non-capturing regex alternation group from a symbol set."""
        escaped = [re.escape(s) for s in sorted(symbols)]
        return "(?:" + "|".join(escaped) + ")"
