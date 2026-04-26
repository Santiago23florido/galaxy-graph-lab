from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..core import Cell, PuzzleData, PuzzleSolveResult, solve_puzzle


@dataclass(slots=True)
class SolverSessionState:
    """Mutable UI state for requesting, caching, and displaying solver results."""

    solver_result: PuzzleSolveResult | None = None
    solver_status_label: str = "not_requested"
    solver_message: str = "The solver has not been requested yet."
    solution_visible: bool = False
    solution_loaded_into_board: bool = False
    solver_result_requested: bool = False

    @property
    def solver_result_cached(self) -> bool:
        return self.solver_result is not None

    @property
    def board_source_label(self) -> str:
        if self.solution_loaded_into_board:
            return "solver"
        return "player"

    def request_solution(
        self,
        puzzle_data: PuzzleData,
        *,
        options: Mapping[str, object] | None = None,
    ) -> PuzzleSolveResult:
        self.solver_result_requested = True
        self.solver_result = solve_puzzle(puzzle_data, options=options)
        self.solver_status_label = self.solver_result.status_label
        self.solver_message = self.solver_result.message
        return self.solver_result

    def solver_assignment_by_cell(self) -> Mapping[Cell, str] | None:
        if self.solver_result is None or self.solver_result.assignment is None:
            return None
        return self.solver_result.assignment.assigned_center_by_cell

    def mark_solution_loaded(self) -> None:
        self.solution_visible = True
        self.solution_loaded_into_board = True

    def mark_player_controlled(self) -> None:
        self.solution_visible = False
        self.solution_loaded_into_board = False


__all__ = ["SolverSessionState"]
