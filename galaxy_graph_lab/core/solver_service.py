from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .milp import GalaxyAssignment, solve_flow_model
from .model_data import PuzzleData


DEFAULT_SOLVER_BACKEND = "exact_flow"
SOLVER_STATUS_SOLVED = "solved"
SOLVER_STATUS_INFEASIBLE = "infeasible"
SOLVER_STATUS_ERROR = "solver_error"
SOLVER_STATUS_BACKEND_UNAVAILABLE = "backend_unavailable"
SOLVER_STATUS_UNSUPPORTED_BACKEND = "unsupported_backend"


@dataclass(frozen=True, slots=True)
class PuzzleSolveResult:
    """Stable top-level solver result returned to the rest of the application."""

    success: bool
    backend_name: str
    status_code: int
    status_label: str
    message: str
    assignment: GalaxyAssignment | None
    objective_value: float | None
    mip_gap: float | None
    mip_node_count: int | None


def _solver_failure(
    *,
    backend_name: str,
    status_code: int,
    status_label: str,
    message: str,
) -> PuzzleSolveResult:
    return PuzzleSolveResult(
        success=False,
        backend_name=backend_name,
        status_code=status_code,
        status_label=status_label,
        message=message,
        assignment=None,
        objective_value=None,
        mip_gap=None,
        mip_node_count=None,
    )


def _normalize_exact_flow_failure_message(raw_message: str) -> tuple[str, str]:
    lowered = raw_message.lower()
    if "infeasible" in lowered or "no feasible" in lowered:
        return (
            SOLVER_STATUS_INFEASIBLE,
            "No feasible solution exists for this puzzle.",
        )
    return (
        SOLVER_STATUS_ERROR,
        f"The solver could not complete successfully: {raw_message}",
    )


def solve_puzzle(
    puzzle_data: PuzzleData,
    *,
    backend: str = DEFAULT_SOLVER_BACKEND,
    options: Mapping[str, object] | None = None,
) -> PuzzleSolveResult:
    """Solve one puzzle instance through the current canonical exact backend."""

    if backend != DEFAULT_SOLVER_BACKEND:
        return _solver_failure(
            backend_name=backend,
            status_code=-1,
            status_label=SOLVER_STATUS_UNSUPPORTED_BACKEND,
            message=f"Solver backend '{backend}' is not supported.",
        )

    try:
        exact_flow_result = solve_flow_model(puzzle_data, options=options)
    except ModuleNotFoundError as exc:
        return _solver_failure(
            backend_name=backend,
            status_code=-2,
            status_label=SOLVER_STATUS_BACKEND_UNAVAILABLE,
            message=f"Solver backend '{backend}' is unavailable: {exc}.",
        )
    except ImportError as exc:
        return _solver_failure(
            backend_name=backend,
            status_code=-2,
            status_label=SOLVER_STATUS_BACKEND_UNAVAILABLE,
            message=f"Solver backend '{backend}' is unavailable: {exc}.",
        )
    except Exception as exc:
        return _solver_failure(
            backend_name=backend,
            status_code=-3,
            status_label=SOLVER_STATUS_ERROR,
            message=f"The solver raised an internal error: {exc}.",
        )

    if exact_flow_result.success:
        return PuzzleSolveResult(
            success=True,
            backend_name=DEFAULT_SOLVER_BACKEND,
            status_code=exact_flow_result.status,
            status_label=SOLVER_STATUS_SOLVED,
            message="Solution found.",
            assignment=exact_flow_result.assignment,
            objective_value=exact_flow_result.objective_value,
            mip_gap=exact_flow_result.mip_gap,
            mip_node_count=exact_flow_result.mip_node_count,
        )

    status_label, message = _normalize_exact_flow_failure_message(
        exact_flow_result.message
    )
    return PuzzleSolveResult(
        success=exact_flow_result.success,
        backend_name=DEFAULT_SOLVER_BACKEND,
        status_code=exact_flow_result.status,
        status_label=status_label,
        message=message,
        assignment=exact_flow_result.assignment,
        objective_value=exact_flow_result.objective_value,
        mip_gap=exact_flow_result.mip_gap,
        mip_node_count=exact_flow_result.mip_node_count,
    )


__all__ = [
    "DEFAULT_SOLVER_BACKEND",
    "PuzzleSolveResult",
    "SOLVER_STATUS_BACKEND_UNAVAILABLE",
    "SOLVER_STATUS_ERROR",
    "SOLVER_STATUS_INFEASIBLE",
    "SOLVER_STATUS_SOLVED",
    "SOLVER_STATUS_UNSUPPORTED_BACKEND",
    "solve_puzzle",
]
