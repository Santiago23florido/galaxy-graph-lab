from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .board import Cell
from .milp import FlowMilpModel, GalaxyAssignment, solve_flow_model
from .milp.base_model import _build_exact_constraint
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
    solution_mode: str = "plain_exact"
    preferred_assignment_count: int = 0
    matched_preference_count: int | None = None
    mismatch_count: int | None = None


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


def _freeze_preferred_assignment(
    puzzle_data: PuzzleData,
    preferred_assignment_by_cell: Mapping[Cell, str] | None,
) -> dict[Cell, str]:
    if preferred_assignment_by_cell is None:
        return {}

    frozen_assignment = dict(preferred_assignment_by_cell)
    known_center_ids = set(puzzle_data.center_by_id)
    for cell, center_id in frozen_assignment.items():
        if not puzzle_data.board.contains(cell):
            raise ValueError(f"Preferred assignment contains a cell outside the board: {cell}")
        if center_id not in known_center_ids:
            raise ValueError(f"Preferred assignment contains an unknown center id: {center_id}")
    return frozen_assignment


def _required_assignment_constraint(
    model: FlowMilpModel,
    required_assignment_by_cell: Mapping[Cell, str],
):
    rows = [
        (
            [model.assignment_variable_index(cell, center_id)],
            [1.0],
            1.0,
        )
        for cell, center_id in required_assignment_by_cell.items()
    ]
    return _build_exact_constraint(model.num_variables, rows)


def _preference_objective(
    model: FlowMilpModel,
    preferred_assignment_by_cell: Mapping[Cell, str],
) -> tuple[float, ...]:
    objective = [0.0] * model.num_variables
    for cell, center_id in preferred_assignment_by_cell.items():
        objective[model.assignment_variable_index(cell, center_id)] = -1.0
    return tuple(objective)


def _count_preference_matches(
    assignment: GalaxyAssignment | None,
    preferred_assignment_by_cell: Mapping[Cell, str],
) -> int | None:
    if assignment is None:
        return None
    return sum(
        1
        for cell, center_id in preferred_assignment_by_cell.items()
        if assignment.assigned_center_by_cell.get(cell) == center_id
    )


def solve_puzzle(
    puzzle_data: PuzzleData,
    *,
    backend: str = DEFAULT_SOLVER_BACKEND,
    options: Mapping[str, object] | None = None,
    preferred_assignment_by_cell: Mapping[Cell, str] | None = None,
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
        preferred_assignment = _freeze_preferred_assignment(
            puzzle_data,
            preferred_assignment_by_cell,
        )
        if not preferred_assignment:
            exact_flow_result = solve_flow_model(puzzle_data, options=options)
        else:
            model = FlowMilpModel.from_puzzle_data(puzzle_data)
            required_constraint = _required_assignment_constraint(model, preferred_assignment)
            exact_flow_result = model.solve(
                options=options,
                extra_constraints=()
                if required_constraint is None
                else (required_constraint,),
            )
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
        success_message = "Solution found."
        solution_mode = "plain_exact"
        matched_preference_count = _count_preference_matches(
            exact_flow_result.assignment,
            preferred_assignment,
        )
        mismatch_count = None
        if preferred_assignment:
            success_message = "Solution found and it keeps all current selections."
            solution_mode = "guided_exact"
            mismatch_count = 0
        return PuzzleSolveResult(
            success=True,
            backend_name=DEFAULT_SOLVER_BACKEND,
            status_code=exact_flow_result.status,
            status_label=SOLVER_STATUS_SOLVED,
            message=success_message,
            assignment=exact_flow_result.assignment,
            objective_value=exact_flow_result.objective_value,
            mip_gap=exact_flow_result.mip_gap,
            mip_node_count=exact_flow_result.mip_node_count,
            solution_mode=solution_mode,
            preferred_assignment_count=len(preferred_assignment),
            matched_preference_count=matched_preference_count,
            mismatch_count=mismatch_count,
        )

    status_label, message = _normalize_exact_flow_failure_message(
        exact_flow_result.message
    )
    if preferred_assignment and status_label == SOLVER_STATUS_INFEASIBLE:
        try:
            model = FlowMilpModel.from_puzzle_data(puzzle_data)
            fallback_result = model.solve(
                options=options,
                objective=_preference_objective(model, preferred_assignment),
            )
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

        if fallback_result.success:
            matched_preference_count = _count_preference_matches(
                fallback_result.assignment,
                preferred_assignment,
            )
            mismatch_count = len(preferred_assignment) - int(matched_preference_count or 0)
            return PuzzleSolveResult(
                success=True,
                backend_name=DEFAULT_SOLVER_BACKEND,
                status_code=fallback_result.status,
                status_label=SOLVER_STATUS_SOLVED,
                message=(
                    "Current selections cannot all be satisfied. "
                    f"Loaded the closest solution with {mismatch_count} mismatch(es)."
                ),
                assignment=fallback_result.assignment,
                objective_value=fallback_result.objective_value,
                mip_gap=fallback_result.mip_gap,
                mip_node_count=fallback_result.mip_node_count,
                solution_mode="guided_min_mismatch",
                preferred_assignment_count=len(preferred_assignment),
                matched_preference_count=matched_preference_count,
                mismatch_count=mismatch_count,
            )

        status_label, message = _normalize_exact_flow_failure_message(
            fallback_result.message
        )
        exact_flow_result = fallback_result

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
        solution_mode="plain_exact",
        preferred_assignment_count=len(preferred_assignment),
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
