from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from scipy.optimize import LinearConstraint
from scipy.sparse import coo_array

from .board import Cell
from .milp import (
    CallbackParallelMilpModel,
    FlowMilpModel,
    GalaxyAssignment,
    HeuristicOrbitSolveResult,
    solve_callback_parallel_model,
    solve_flow_model,
    solve_heuristic_orbit_model,
)
from .milp.base_model import _build_exact_constraint
from .model_data import PuzzleData


EXACT_FLOW_SOLVER_BACKEND = "exact_flow"
PARALLEL_CALLBACK_SOLVER_BACKEND = "parallel_callback"
HEURISTIC_ORBIT_SOLVER_BACKEND = "heuristic_orbit"
SUPPORTED_SOLVER_BACKENDS = frozenset(
    {
        EXACT_FLOW_SOLVER_BACKEND,
        PARALLEL_CALLBACK_SOLVER_BACKEND,
        HEURISTIC_ORBIT_SOLVER_BACKEND,
    }
)
DEFAULT_SOLVER_BACKEND = EXACT_FLOW_SOLVER_BACKEND
DEFAULT_SOLVER_TIME_LIMIT_BY_BACKEND = MappingProxyType(
    {
        EXACT_FLOW_SOLVER_BACKEND: 0.5,
        PARALLEL_CALLBACK_SOLVER_BACKEND: 10.0,
        HEURISTIC_ORBIT_SOLVER_BACKEND: 100.0,
    }
)
SOLVER_STATUS_SOLVED = "solved"
SOLVER_STATUS_INFEASIBLE = "infeasible"
SOLVER_STATUS_ERROR = "solver_error"
SOLVER_STATUS_BACKEND_UNAVAILABLE = "backend_unavailable"
SOLVER_STATUS_UNSUPPORTED_BACKEND = "unsupported_backend"


_AssignmentIndexedModel = FlowMilpModel | CallbackParallelMilpModel


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


def _resolve_backend_options(
    backend: str,
    options: Mapping[str, object] | None,
) -> Mapping[str, object]:
    resolved_options = {} if options is None else dict(options)
    if not any(
        key in resolved_options
        for key in ("time_limit", "timelimit", "timeLimit")
    ):
        resolved_options["time_limit"] = DEFAULT_SOLVER_TIME_LIMIT_BY_BACKEND[backend]
    return dict(resolved_options)


def _normalize_common_failure_message(
    raw_message: str,
    *,
    extra_infeasible_tokens: tuple[str, ...] = (),
) -> tuple[str, str]:
    lowered = raw_message.lower()
    if (
        "time limit" in lowered
        or "timed out" in lowered
        or "timeout" in lowered
        or "infeasible" in lowered
        or "no feasible" in lowered
        or any(token in lowered for token in extra_infeasible_tokens)
    ):
        return (
            SOLVER_STATUS_INFEASIBLE,
            "No feasible solution exists for this puzzle.",
        )
    return (
        SOLVER_STATUS_ERROR,
        f"The solver could not complete successfully: {raw_message}",
    )


def _normalize_exact_flow_failure_message(raw_message: str) -> tuple[str, str]:
    return _normalize_common_failure_message(raw_message)


def _normalize_parallel_callback_failure_message(raw_message: str) -> tuple[str, str]:
    return _normalize_common_failure_message(
        raw_message,
        extra_infeasible_tokens=(
            "integer infeasible",
            "primal infeasible",
            "infeasible or unbounded",
            "no solution exists",
            "no integer solution",
        ),
    )


def _normalize_heuristic_orbit_failure_message(raw_message: str) -> tuple[str, str]:
    return _normalize_common_failure_message(
        raw_message,
        extra_infeasible_tokens=(
            "no valid solution",
            "exhausted",
            "heuristic orbit search",
        ),
    )


def _freeze_preferred_assignment(
    puzzle_data: PuzzleData,
    assignment_by_cell: Mapping[Cell, str] | None,
) -> dict[Cell, str]:
    if assignment_by_cell is None:
        return {}

    frozen_assignment = dict(assignment_by_cell)
    known_center_ids = set(puzzle_data.center_by_id)
    for cell, center_id in frozen_assignment.items():
        if not puzzle_data.board.contains(cell):
            raise ValueError(f"Preferred assignment contains a cell outside the board: {cell}")
        if center_id not in known_center_ids:
            raise ValueError(f"Preferred assignment contains an unknown center id: {center_id}")
    return frozen_assignment


def _required_assignment_constraint(
    model: _AssignmentIndexedModel,
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


def _minimum_mismatch_constraint(
    model: _AssignmentIndexedModel,
    avoid_assignment_by_cell: Mapping[Cell, str],
    minimum_mismatches: int,
) -> LinearConstraint | None:
    if minimum_mismatches <= 0:
        return None
    if minimum_mismatches > len(avoid_assignment_by_cell):
        raise ValueError("minimum_mismatches cannot exceed the guided cell count.")

    columns = [
        model.assignment_variable_index(cell, center_id)
        for cell, center_id in avoid_assignment_by_cell.items()
    ]
    matrix = coo_array(
        (
            np.ones(len(columns), dtype=float),
            (
                np.zeros(len(columns), dtype=int),
                np.asarray(columns, dtype=int),
            ),
        ),
        shape=(1, model.num_variables),
    ).tocsc()
    return LinearConstraint(
        matrix,
        -np.inf,
        np.asarray([len(avoid_assignment_by_cell) - minimum_mismatches], dtype=float),
    )


def _preference_objective(
    model: _AssignmentIndexedModel,
    preferred_assignment_by_cell: Mapping[Cell, str],
    avoid_assignment_by_cell: Mapping[Cell, str] | None = None,
) -> tuple[float, ...]:
    objective = [0.0] * model.num_variables
    for cell, center_id in preferred_assignment_by_cell.items():
        objective[model.assignment_variable_index(cell, center_id)] = -1.0
    if avoid_assignment_by_cell is not None:
        for cell, center_id in avoid_assignment_by_cell.items():
            objective[model.assignment_variable_index(cell, center_id)] += 1.0
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


def _solve_with_parallel_callback_backend(
    puzzle_data: PuzzleData,
    *,
    options: Mapping[str, object] | None = None,
    preferred_assignment_by_cell: Mapping[Cell, str] | None = None,
    avoid_assignment_by_cell: Mapping[Cell, str] | None = None,
    minimum_mismatches_against_avoid: int | None = None,
) -> PuzzleSolveResult:
    """Solve one puzzle instance with the callback-parallel backend."""

    backend = PARALLEL_CALLBACK_SOLVER_BACKEND

    try:
        preferred_assignment = _freeze_preferred_assignment(
            puzzle_data,
            preferred_assignment_by_cell,
        )
        avoid_assignment = _freeze_preferred_assignment(
            puzzle_data,
            avoid_assignment_by_cell,
        )
        if not preferred_assignment and not avoid_assignment:
            callback_result = solve_callback_parallel_model(puzzle_data, options=options)
        elif preferred_assignment and not avoid_assignment:
            model = CallbackParallelMilpModel.from_puzzle_data(puzzle_data)
            required_constraint = _required_assignment_constraint(model, preferred_assignment)
            callback_result = model.solve(
                options=options,
                extra_constraints=()
                if required_constraint is None
                else (required_constraint,),
            )
        else:
            model = CallbackParallelMilpModel.from_puzzle_data(puzzle_data)
            mismatch_constraint = None
            if minimum_mismatches_against_avoid is not None:
                mismatch_constraint = _minimum_mismatch_constraint(
                    model,
                    avoid_assignment,
                    minimum_mismatches_against_avoid,
                )
            callback_result = model.solve(
                options=options,
                objective=_preference_objective(
                    model,
                    preferred_assignment,
                    avoid_assignment,
                ),
                extra_constraints=()
                if mismatch_constraint is None
                else (mismatch_constraint,),
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

    if callback_result.success:
        success_message = "Solution found."
        solution_mode = "plain_exact"
        matched_preference_count = _count_preference_matches(
            callback_result.assignment,
            preferred_assignment,
        )
        mismatch_count = None
        if preferred_assignment and avoid_assignment:
            success_message = "Solution found and it follows the requested shape guidance."
            solution_mode = "guided_shape"
            mismatch_count = len(preferred_assignment) - int(matched_preference_count or 0)
        elif preferred_assignment:
            success_message = "Solution found and it keeps all current selections."
            solution_mode = "guided_exact"
            mismatch_count = 0
        return PuzzleSolveResult(
            success=True,
            backend_name=backend,
            status_code=callback_result.status,
            status_label=SOLVER_STATUS_SOLVED,
            message=success_message,
            assignment=callback_result.assignment,
            objective_value=callback_result.objective_value,
            mip_gap=callback_result.mip_gap,
            mip_node_count=callback_result.mip_node_count,
            solution_mode=solution_mode,
            preferred_assignment_count=len(preferred_assignment),
            matched_preference_count=matched_preference_count,
            mismatch_count=mismatch_count,
        )

    status_label, message = _normalize_parallel_callback_failure_message(
        callback_result.message
    )
    if preferred_assignment and not avoid_assignment and status_label == SOLVER_STATUS_INFEASIBLE:
        try:
            model = CallbackParallelMilpModel.from_puzzle_data(puzzle_data)
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
                backend_name=backend,
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

        status_label, message = _normalize_parallel_callback_failure_message(
            fallback_result.message
        )
        callback_result = fallback_result

    return PuzzleSolveResult(
        success=callback_result.success,
        backend_name=backend,
        status_code=callback_result.status,
        status_label=status_label,
        message=message,
        assignment=callback_result.assignment,
        objective_value=callback_result.objective_value,
        mip_gap=callback_result.mip_gap,
        mip_node_count=callback_result.mip_node_count,
        solution_mode="plain_exact",
        preferred_assignment_count=len(preferred_assignment),
    )

def _solve_with_heuristic_orbit_backend(
    puzzle_data: PuzzleData,
    *,
    options: Mapping[str, object] | None = None,
    preferred_assignment_by_cell: Mapping[Cell, str] | None = None,
    avoid_assignment_by_cell: Mapping[Cell, str] | None = None,
    minimum_mismatches_against_avoid: int | None = None,
) -> PuzzleSolveResult:
    """Solve one puzzle instance with the orbit-based heuristic backend."""

    backend = HEURISTIC_ORBIT_SOLVER_BACKEND

    try:
        preferred_assignment = _freeze_preferred_assignment(
            puzzle_data,
            preferred_assignment_by_cell,
        )
        avoid_assignment = _freeze_preferred_assignment(
            puzzle_data,
            avoid_assignment_by_cell,
        )
        heuristic_result = solve_heuristic_orbit_model(
            puzzle_data,
            options=options,
            preferred_assignment_by_cell=preferred_assignment or None,
            avoid_assignment_by_cell=avoid_assignment or None,
            minimum_mismatches_against_avoid=minimum_mismatches_against_avoid,
            require_preferred_assignment=bool(preferred_assignment and not avoid_assignment),
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

    if heuristic_result.success:
        success_message = "Solution found."
        solution_mode = "plain_exact"
        matched_preference_count = _count_preference_matches(
            heuristic_result.assignment,
            preferred_assignment,
        )
        mismatch_count = None
        if preferred_assignment and avoid_assignment:
            success_message = "Solution found and it follows the requested shape guidance."
            solution_mode = "guided_shape"
            mismatch_count = len(preferred_assignment) - int(matched_preference_count or 0)
        elif preferred_assignment:
            success_message = "Solution found and it keeps all current selections."
            solution_mode = "guided_exact"
            mismatch_count = 0
        return PuzzleSolveResult(
            success=True,
            backend_name=backend,
            status_code=heuristic_result.status,
            status_label=SOLVER_STATUS_SOLVED,
            message=success_message,
            assignment=heuristic_result.assignment,
            objective_value=heuristic_result.objective_value,
            mip_gap=heuristic_result.mip_gap,
            mip_node_count=heuristic_result.mip_node_count,
            solution_mode=solution_mode,
            preferred_assignment_count=len(preferred_assignment),
            matched_preference_count=matched_preference_count,
            mismatch_count=mismatch_count,
        )

    status_label, message = _normalize_heuristic_orbit_failure_message(
        heuristic_result.message
    )
    if preferred_assignment and not avoid_assignment and status_label == SOLVER_STATUS_INFEASIBLE:
        try:
            fallback_result = solve_heuristic_orbit_model(
                puzzle_data,
                options=options,
                preferred_assignment_by_cell=preferred_assignment or None,
                avoid_assignment_by_cell=None,
                minimum_mismatches_against_avoid=None,
                require_preferred_assignment=False,
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
                backend_name=backend,
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

        status_label, message = _normalize_heuristic_orbit_failure_message(
            fallback_result.message
        )
        heuristic_result = fallback_result

    return PuzzleSolveResult(
        success=heuristic_result.success,
        backend_name=backend,
        status_code=heuristic_result.status,
        status_label=status_label,
        message=message,
        assignment=heuristic_result.assignment,
        objective_value=heuristic_result.objective_value,
        mip_gap=heuristic_result.mip_gap,
        mip_node_count=heuristic_result.mip_node_count,
        solution_mode="plain_exact",
        preferred_assignment_count=len(preferred_assignment),
    )


def _solve_with_exact_flow_backend(
    puzzle_data: PuzzleData,
    *,
    options: Mapping[str, object] | None = None,
    preferred_assignment_by_cell: Mapping[Cell, str] | None = None,
    avoid_assignment_by_cell: Mapping[Cell, str] | None = None,
    minimum_mismatches_against_avoid: int | None = None,
) -> PuzzleSolveResult:
    """Solve one puzzle instance with the current exact-flow backend."""

    backend = EXACT_FLOW_SOLVER_BACKEND

    try:
        preferred_assignment = _freeze_preferred_assignment(
            puzzle_data,
            preferred_assignment_by_cell,
        )
        avoid_assignment = _freeze_preferred_assignment(
            puzzle_data,
            avoid_assignment_by_cell,
        )
        if not preferred_assignment and not avoid_assignment:
            exact_flow_result = solve_flow_model(puzzle_data, options=options)
        elif preferred_assignment and not avoid_assignment:
            model = FlowMilpModel.from_puzzle_data(puzzle_data)
            required_constraint = _required_assignment_constraint(model, preferred_assignment)
            exact_flow_result = model.solve(
                options=options,
                extra_constraints=()
                if required_constraint is None
                else (required_constraint,),
            )
        else:
            model = FlowMilpModel.from_puzzle_data(puzzle_data)
            mismatch_constraint = None
            if minimum_mismatches_against_avoid is not None:
                mismatch_constraint = _minimum_mismatch_constraint(
                    model,
                    avoid_assignment,
                    minimum_mismatches_against_avoid,
                )
            exact_flow_result = model.solve(
                options=options,
                objective=_preference_objective(
                    model,
                    preferred_assignment,
                    avoid_assignment,
                ),
                extra_constraints=()
                if mismatch_constraint is None
                else (mismatch_constraint,),
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
        if preferred_assignment and avoid_assignment:
            success_message = "Solution found and it follows the requested shape guidance."
            solution_mode = "guided_shape"
            mismatch_count = len(preferred_assignment) - int(matched_preference_count or 0)
        elif preferred_assignment:
            success_message = "Solution found and it keeps all current selections."
            solution_mode = "guided_exact"
            mismatch_count = 0
        return PuzzleSolveResult(
            success=True,
            backend_name=backend,
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
    if preferred_assignment and not avoid_assignment and status_label == SOLVER_STATUS_INFEASIBLE:
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
                backend_name=backend,
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
        backend_name=backend,
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


def solve_puzzle(
    puzzle_data: PuzzleData,
    *,
    backend: str = DEFAULT_SOLVER_BACKEND,
    options: Mapping[str, object] | None = None,
    preferred_assignment_by_cell: Mapping[Cell, str] | None = None,
    avoid_assignment_by_cell: Mapping[Cell, str] | None = None,
    minimum_mismatches_against_avoid: int | None = None,
) -> PuzzleSolveResult:
    """Solve one puzzle instance through one supported public backend."""

    if backend not in SUPPORTED_SOLVER_BACKENDS:
        return _solver_failure(
            backend_name=backend,
            status_code=-1,
            status_label=SOLVER_STATUS_UNSUPPORTED_BACKEND,
            message=f"Solver backend '{backend}' is not supported.",
        )
    resolved_options = _resolve_backend_options(backend, options)
    if backend == EXACT_FLOW_SOLVER_BACKEND:
        return _solve_with_exact_flow_backend(
            puzzle_data,
            options=resolved_options,
            preferred_assignment_by_cell=preferred_assignment_by_cell,
            avoid_assignment_by_cell=avoid_assignment_by_cell,
            minimum_mismatches_against_avoid=minimum_mismatches_against_avoid,
        )
    if backend == PARALLEL_CALLBACK_SOLVER_BACKEND:
        return _solve_with_parallel_callback_backend(
            puzzle_data,
            options=resolved_options,
            preferred_assignment_by_cell=preferred_assignment_by_cell,
            avoid_assignment_by_cell=avoid_assignment_by_cell,
            minimum_mismatches_against_avoid=minimum_mismatches_against_avoid,
        )
    if backend == HEURISTIC_ORBIT_SOLVER_BACKEND:
        return _solve_with_heuristic_orbit_backend(
            puzzle_data,
            options=resolved_options,
            preferred_assignment_by_cell=preferred_assignment_by_cell,
            avoid_assignment_by_cell=avoid_assignment_by_cell,
            minimum_mismatches_against_avoid=minimum_mismatches_against_avoid,
        )
    return _solver_failure(
        backend_name=backend,
        status_code=-1,
        status_label=SOLVER_STATUS_UNSUPPORTED_BACKEND,
        message=f"Solver backend '{backend}' is not supported.",
    )


__all__ = [
    "DEFAULT_SOLVER_BACKEND",
    "DEFAULT_SOLVER_TIME_LIMIT_BY_BACKEND",
    "EXACT_FLOW_SOLVER_BACKEND",
    "HEURISTIC_ORBIT_SOLVER_BACKEND",
    "PARALLEL_CALLBACK_SOLVER_BACKEND",
    "PuzzleSolveResult",
    "SOLVER_STATUS_BACKEND_UNAVAILABLE",
    "SOLVER_STATUS_ERROR",
    "SOLVER_STATUS_INFEASIBLE",
    "SOLVER_STATUS_SOLVED",
    "SOLVER_STATUS_UNSUPPORTED_BACKEND",
    "SUPPORTED_SOLVER_BACKENDS",
    "solve_puzzle",
]
