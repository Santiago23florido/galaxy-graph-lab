from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .milp import GalaxyAssignment, solve_flow_model
from .model_data import PuzzleData


DEFAULT_SOLVER_BACKEND = "exact_flow"


@dataclass(frozen=True, slots=True)
class PuzzleSolveResult:
    """Stable top-level solver result returned to the rest of the application."""

    success: bool
    backend_name: str
    status_code: int
    message: str
    assignment: GalaxyAssignment | None
    objective_value: float | None
    mip_gap: float | None
    mip_node_count: int | None


def solve_puzzle(
    puzzle_data: PuzzleData,
    *,
    options: Mapping[str, object] | None = None,
) -> PuzzleSolveResult:
    """Solve one puzzle instance through the current canonical exact backend."""

    exact_flow_result = solve_flow_model(puzzle_data, options=options)
    return PuzzleSolveResult(
        success=exact_flow_result.success,
        backend_name=DEFAULT_SOLVER_BACKEND,
        status_code=exact_flow_result.status,
        message=exact_flow_result.message,
        assignment=exact_flow_result.assignment,
        objective_value=exact_flow_result.objective_value,
        mip_gap=exact_flow_result.mip_gap,
        mip_node_count=exact_flow_result.mip_node_count,
    )


__all__ = [
    "DEFAULT_SOLVER_BACKEND",
    "PuzzleSolveResult",
    "solve_puzzle",
]
