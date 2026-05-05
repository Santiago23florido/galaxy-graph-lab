from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..core import (
    DEFAULT_SOLVER_BACKEND,
    Cell,
    PuzzleData,
    PuzzleSolveResult,
    solve_puzzle,
)


@dataclass(slots=True)
class SolverSessionState:
    """Mutable UI state for requesting, caching, and displaying solver results."""

    solver_backend: str = DEFAULT_SOLVER_BACKEND
    solver_result: PuzzleSolveResult | None = None
    solver_status_label: str = "not_requested"
    solver_message: str = "The solver has not been requested yet."
    solution_visible: bool = False
    solution_loaded_into_board: bool = False
    solver_result_requested: bool = False
    manual_assignment_snapshot: dict[Cell, str] | None = None
    manual_edits_after_solution: bool = False

    @property
    def solver_result_cached(self) -> bool:
        return self.solver_result is not None

    @property
    def board_mode_label(self) -> str:
        if self.solution_loaded_into_board and self.manual_edits_after_solution:
            return "mixed"
        if self.solution_loaded_into_board:
            return "solver-loaded"
        return "manual"

    @property
    def can_restore_manual_snapshot(self) -> bool:
        return self.manual_assignment_snapshot is not None

    def request_solution(
        self,
        puzzle_data: PuzzleData,
        *,
        backend: str | None = None,
        options: Mapping[str, object] | None = None,
        preferred_assignment_by_cell: Mapping[Cell, str] | None = None,
    ) -> PuzzleSolveResult:
        selected_backend = self.solver_backend if backend is None else backend
        self.solver_backend = selected_backend
        self.solver_result_requested = True
        self.solver_result = solve_puzzle(
            puzzle_data,
            backend=selected_backend,
            options=options,
            preferred_assignment_by_cell=preferred_assignment_by_cell,
        )
        self.solver_status_label = self.solver_result.status_label
        self.solver_message = self.solver_result.message
        return self.solver_result

    def capture_manual_snapshot(
        self,
        assigned_center_by_cell: Mapping[Cell, str],
    ) -> None:
        self.manual_assignment_snapshot = dict(assigned_center_by_cell)

    def solver_assignment_by_cell(self) -> Mapping[Cell, str] | None:
        if self.solver_result is None or self.solver_result.assignment is None:
            return None
        return self.solver_result.assignment.assigned_center_by_cell

    def comparison_reference_assignment_by_cell(
        self,
        current_assignment_by_cell: Mapping[Cell, str],
    ) -> Mapping[Cell, str]:
        if (
            self.solution_loaded_into_board
            and not self.manual_edits_after_solution
            and self.manual_assignment_snapshot is not None
        ):
            return dict(self.manual_assignment_snapshot)
        return current_assignment_by_cell

    def mark_solution_loaded(self) -> None:
        self.solution_visible = True
        self.solution_loaded_into_board = True
        self.manual_edits_after_solution = False

    def mark_manual_edit(self) -> None:
        if self.solution_loaded_into_board:
            self.solution_visible = True
            self.manual_edits_after_solution = True

    def clear_solution_view(self) -> None:
        self.solution_visible = False
        self.solution_loaded_into_board = False
        self.manual_edits_after_solution = False

    def restore_manual_snapshot(self) -> Mapping[Cell, str] | None:
        if self.manual_assignment_snapshot is None:
            return None

        snapshot = dict(self.manual_assignment_snapshot)
        self.manual_assignment_snapshot = None
        self.clear_solution_view()
        return snapshot

    def mark_player_controlled(self) -> None:
        self.clear_solution_view()

    def discard_manual_snapshot(self) -> None:
        self.manual_assignment_snapshot = None


__all__ = ["SolverSessionState"]
