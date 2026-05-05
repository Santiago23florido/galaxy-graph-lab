from __future__ import annotations

from dataclasses import dataclass

try:
    from ..core import (
        BoardSpec,
        CenterSpec,
        PuzzleData,
        PuzzleSolveResult,
        StoredPuzzleInstance,
    )
except ImportError:
    from core import (
        BoardSpec,
        CenterSpec,
        PuzzleData,
        PuzzleSolveResult,
        StoredPuzzleInstance,
    )


@dataclass(frozen=True, slots=True)
class FixedPuzzle:
    """One fixed puzzle descriptor bundled with the Pygame MVP."""

    name: str
    puzzle_data: PuzzleData
    stored_instance: StoredPuzzleInstance | None = None
    cached_solution: PuzzleSolveResult | None = None


def load_phase_a_puzzle() -> FixedPuzzle:
    """Return the fixed puzzle used by the Phase A window."""

    board = BoardSpec(rows=7, cols=7)
    centers = (
        CenterSpec.from_coordinates("A", 1, 1),
        CenterSpec.from_coordinates("B", 1, 4.5),
        CenterSpec.from_coordinates("C", 3.5,3),
        CenterSpec.from_coordinates("D", 5.5, 5),
        CenterSpec.from_coordinates("E", 5.5, 1.5),
    )

    return FixedPuzzle(
        name="Phase A Demo",
        puzzle_data=PuzzleData.from_specs(board, centers),
    )
