from __future__ import annotations

from app.domain.phonology.backends.base import Backend
from app.domain.phonology.ir import SoundChangeRule


class NativeBackend(Backend):
    """Pure Python list-iteration backend.

    Intended for unit testing and correctness verification — not for
    production-scale batch processing. All other backends must produce
    identical output to this reference implementation.
    """

    def apply(self, rule: SoundChangeRule, sequence: list[str]) -> list[str]:
        if not sequence:
            return []

        target_syms = rule.target_symbols
        before_syms = rule.env_before_symbols
        after_syms = rule.env_after_symbols
        word_initial = rule.env_flags.get("word_initial", False)
        word_final = rule.env_flags.get("word_final", False)

        result: list[str] = []
        i = 0
        n = len(sequence)

        while i < n:
            sym = sequence[i]

            if sym not in target_syms:
                result.append(sym)
                i += 1
                continue

            prev_sym = sequence[i - 1] if i > 0 else None
            next_sym = sequence[i + 1] if i < n - 1 else None

            if word_initial and i != 0:
                result.append(sym)
                i += 1
                continue

            if word_final and i != n - 1:
                result.append(sym)
                i += 1
                continue

            if before_syms is not None:
                if prev_sym is None or prev_sym not in before_syms:
                    result.append(sym)
                    i += 1
                    continue

            if after_syms is not None:
                if next_sym is None or next_sym not in after_syms:
                    result.append(sym)
                    i += 1
                    continue

            if rule.op == "delete":
                i += 1
                continue
            elif rule.op == "change":
                new_sym = rule.output_map.get(sym, sym)
                result.append(new_sym)
                i += 1
            elif rule.op == "insert":
                result.append(sym)
                if rule.output_map:
                    insert_sym = next(iter(rule.output_map.values()))
                    result.append(insert_sym)
                i += 1
            else:
                result.append(sym)
                i += 1

        return result
