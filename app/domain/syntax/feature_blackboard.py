from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FeatureBlackboard:
    """Sentence-level feature accumulator for Agreement computation.

    The planner writes subject features (person, number, gender, …) during
    subject processing; the verb inflection step reads those features back to
    select the correct agreement morpheme.

    Typical lifecycle per sentence::

        board = FeatureBlackboard()
        board.write("person", "1")
        board.write("number", "sg")
        person = board.read("person")  # "1"
        board.clear()                  # ready for next sentence
    """

    _state: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def write(self, feature: str, value: str) -> None:
        self._state[feature] = value

    def read(self, feature: str) -> str | None:
        return self._state.get(feature)

    def read_or(self, feature: str, default: str) -> str:
        return self._state.get(feature, default)

    def clear(self) -> None:
        self._state.clear()

    def snapshot(self) -> dict[str, str]:
        return dict(self._state)

    def __contains__(self, feature: str) -> bool:
        return feature in self._state
