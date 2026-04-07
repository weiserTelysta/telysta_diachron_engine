from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from app.domain.phonology.ir import SoundChangeRule

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    PRIORITY = "priority"
    COVERAGE = "coverage"
    LEGALITY = "legality"
    SEMANTIC = "semantic"


@dataclass
class ConflictReport:
    conflict_type: ConflictType
    rules_involved: list[str]
    resolution: str
    winning_rule: str | None = None


class ConflictResolver:
    """Handles the four conflict types defined in the spec (§2.5.3).

    Priority conflict:   Two rules fire on the same token; highest priority wins.
    Coverage conflict:   Rule A output triggers rule B; strict single-pass scan.
    Legality conflict:   Rule output violates phonotactics; delegate to validator.
    Semantic conflict:   Sound change produces a homophone; fire homophone resolver.

    Consumers pass a sorted rule list and optionally register callbacks for
    legality and semantic conflicts.
    """

    def __init__(
        self,
        legality_callback: Callable[[list[str], str], list[str]] | None = None,
        homophone_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self._legality_cb = legality_callback
        self._homophone_cb = homophone_callback

    def resolve_priority(
        self,
        rules: list[SoundChangeRule],
        sequence: list[str],
        apply_fn: Callable[[SoundChangeRule, list[str]], list[str]],
    ) -> tuple[list[str], list[ConflictReport]]:
        """Apply rules in ascending priority order (lower int = higher priority).

        When two rules have overlapping targets on the same token, the first
        applied rule wins because the token is already transformed. Single-pass
        scan guarantees no feeding/bleeding without explicit configuration.
        """
        sorted_rules = sorted(rules, key=lambda r: r.priority)
        reports: list[ConflictReport] = []
        current = list(sequence)

        for rule in sorted_rules:
            after = apply_fn(rule, current)
            if after != current:
                current = after
        return current, reports

    def resolve_coverage(
        self,
        rules: list[SoundChangeRule],
        sequence: list[str],
        apply_fn: Callable[[SoundChangeRule, list[str]], list[str]],
        feeding_mode: bool = False,
    ) -> tuple[list[str], list[ConflictReport]]:
        """Single-pass scan across the rule list.

        feeding_mode=False (default): strict registration-order scan, no
        re-triggering after a token is changed (bleeding/opacity safe).
        feeding_mode=True: iterative until stable (feeding mode, use with care).
        """
        reports: list[ConflictReport] = []
        current = list(sequence)

        if not feeding_mode:
            for rule in rules:
                current = apply_fn(rule, current)
        else:
            max_iter = len(rules) * 2
            for _ in range(max_iter):
                prev = list(current)
                for rule in rules:
                    current = apply_fn(rule, current)
                if current == prev:
                    break

        return current, reports

    def check_legality(
        self,
        sequence: list[str],
        rule_name: str,
        original: list[str],
    ) -> tuple[list[str], ConflictReport | None]:
        """Delegate to legality callback if set; return (repaired_or_original, report)."""
        if self._legality_cb is None:
            return sequence, None

        repaired = self._legality_cb(sequence, rule_name)
        if repaired == sequence:
            return sequence, None

        if repaired == original:
            report = ConflictReport(
                conflict_type=ConflictType.LEGALITY,
                rules_involved=[rule_name],
                resolution="rollback",
                winning_rule=None,
            )
        else:
            report = ConflictReport(
                conflict_type=ConflictType.LEGALITY,
                rules_involved=[rule_name],
                resolution="epenthesis",
                winning_rule=rule_name,
            )
        return repaired, report

    def check_homophone(
        self,
        word_id: str,
        new_form: str,
        existing_forms: dict[str, str],
    ) -> ConflictReport | None:
        """Fire homophone_callback if new_form collides with an existing word."""
        collisions = [wid for wid, form in existing_forms.items() if form == new_form and wid != word_id]
        if not collisions:
            return None

        logger.warning(
            "Homophone collision: %s → %s collides with %s",
            word_id,
            new_form,
            collisions,
        )
        if self._homophone_cb is not None:
            for collision_id in collisions:
                self._homophone_cb(word_id, collision_id)

        return ConflictReport(
            conflict_type=ConflictType.SEMANTIC,
            rules_involved=[word_id] + collisions,
            resolution="homophone_resolver_triggered",
        )
