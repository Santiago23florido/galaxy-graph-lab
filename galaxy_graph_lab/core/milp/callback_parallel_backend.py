from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter

import numpy as np
from scipy.optimize import LinearConstraint
from scipy.sparse import coo_array

from ..model_data import PuzzleData
from .callback_parallel_model import CallbackParallelMilpModel, CallbackParallelSolveResult


def _resolve_thread_count(options: Mapping[str, object] | None) -> int:
    if options is None:
        return 0

    for key in ("threads", "thread_count", "parallel_threads"):
        raw_value = options.get(key)
        if raw_value is None:
            continue
        if not isinstance(raw_value, int) or isinstance(raw_value, bool):
            raise TypeError(f"Solver option '{key}' must be a plain integer.")
        if raw_value < 0:
            raise ValueError(f"Solver option '{key}' must be non-negative.")
        return raw_value
    return 0


def _resolve_time_limit(options: Mapping[str, object] | None) -> float | None:
    if options is None:
        return None

    for key in ("time_limit", "timelimit", "timeLimit"):
        raw_value = options.get(key)
        if raw_value is None:
            continue
        if not isinstance(raw_value, int | float) or isinstance(raw_value, bool):
            raise TypeError(f"Solver option '{key}' must be numeric.")
        if raw_value <= 0:
            raise ValueError(f"Solver option '{key}' must be positive.")
        return float(raw_value)
    return None


def _resolve_mip_gap(options: Mapping[str, object] | None) -> float | None:
    if options is None:
        return None

    for key in ("mip_gap", "mipgap", "relative_gap"):
        raw_value = options.get(key)
        if raw_value is None:
            continue
        if not isinstance(raw_value, int | float) or isinstance(raw_value, bool):
            raise TypeError(f"Solver option '{key}' must be numeric.")
        if raw_value < 0:
            raise ValueError(f"Solver option '{key}' must be non-negative.")
        return float(raw_value)
    return None


def _internal_solver_options(
    options: Mapping[str, object] | None,
) -> Mapping[str, object] | None:
    if options is None:
        return None

    # Keep the public option surface stable even though the backend is internal.
    _resolve_thread_count(options)
    time_limit = _resolve_time_limit(options)
    mip_gap = _resolve_mip_gap(options)

    internal_options: dict[str, object] = {}
    if time_limit is not None:
        internal_options["time_limit"] = time_limit
    if mip_gap is not None:
        internal_options["mip_rel_gap"] = mip_gap
    return internal_options or None


def _base_result_to_callback_result(
    result,
) -> CallbackParallelSolveResult:
    assignment_variable_values = getattr(
        result,
        "assignment_variable_values",
        getattr(result, "variable_values", None),
    )
    directed_flow_values = getattr(result, "directed_flow_values", None)
    source_flow_values = getattr(result, "source_flow_values", None)
    return CallbackParallelSolveResult(
        success=result.success,
        status=result.status,
        message=result.message,
        objective_value=result.objective_value,
        mip_gap=result.mip_gap,
        mip_node_count=result.mip_node_count,
        assignment=result.assignment,
        assignment_variable_values=assignment_variable_values,
        directed_flow_values=directed_flow_values,
        source_flow_values=source_flow_values,
    )


def _assignment_is_connected(
    model: CallbackParallelMilpModel,
    assignment,
) -> bool:
    for center in model.puzzle_data.centers:
        selected_cells = assignment.cells_by_center[center.id]
        if not model.puzzle_data.graph.is_connected(selected_cells):
            return False
    return True


def _solution_exclusion_constraint(
    num_variables: int,
    variable_values: Sequence[float],
) -> LinearConstraint:
    """Exclude one exact 0/1 assignment so the base MILP must try another one."""

    if len(variable_values) != num_variables:
        raise ValueError("Solution vector length does not match the callback model.")

    columns = list(range(num_variables))
    coefficients: list[float] = []
    selected_count = 0.0
    for value in variable_values:
        is_selected = float(value) >= 0.5
        coefficients.append(1.0 if is_selected else -1.0)
        if is_selected:
            selected_count += 1.0

    matrix = coo_array(
        (
            np.asarray(coefficients, dtype=float),
            (
                np.zeros(num_variables, dtype=int),
                np.asarray(columns, dtype=int),
            ),
        ),
        shape=(1, num_variables),
    ).tocsc()
    return LinearConstraint(
        matrix,
        -np.inf,
        np.asarray([selected_count - 1.0], dtype=float),
    )


def _remaining_internal_options(
    base_options: Mapping[str, object] | None,
    *,
    started_at: float,
) -> Mapping[str, object] | None:
    internal_options = dict(base_options or {})
    raw_time_limit = internal_options.get("time_limit")
    if raw_time_limit is None:
        return internal_options or None

    time_limit = float(raw_time_limit)
    remaining = time_limit - (perf_counter() - started_at)
    if remaining <= 0.0:
        remaining = 1e-6
    internal_options["time_limit"] = remaining
    return internal_options


def _finalize_loop_result(
    result: CallbackParallelSolveResult,
    *,
    rejected_incumbent_count: int,
    accumulated_node_count: int | None,
) -> CallbackParallelSolveResult:
    message = result.message
    if rejected_incumbent_count > 0:
        if result.success:
            message = (
                "Connected solution found after rejecting "
                f"{rejected_incumbent_count} disconnected incumbent(s). "
                f"{result.message}"
            )
        elif "infeasible" in result.message.lower():
            message = (
                "The base MILP became infeasible after excluding "
                f"{rejected_incumbent_count} disconnected incumbent(s). "
                f"{result.message}"
            )
        else:
            message = (
                "The callback-style connectivity loop stopped after rejecting "
                f"{rejected_incumbent_count} disconnected incumbent(s). "
                f"{result.message}"
            )

    return CallbackParallelSolveResult(
        success=result.success,
        status=result.status,
        message=message,
        objective_value=result.objective_value,
        mip_gap=result.mip_gap,
        mip_node_count=accumulated_node_count,
        assignment=result.assignment,
        assignment_variable_values=result.assignment_variable_values,
        directed_flow_values=result.directed_flow_values,
        source_flow_values=result.source_flow_values,
    )


def _solve_internal_base_with_connectivity_rejections(
    model: CallbackParallelMilpModel,
    *,
    options: Mapping[str, object] | None,
    objective: Sequence[float] | None,
    extra_constraints: Sequence[LinearConstraint],
) -> CallbackParallelSolveResult:
    """Repeat the base MILP until one incumbent is connected on the grid graph."""

    accumulated_constraints = list(extra_constraints)
    rejected_incumbent_count = 0
    accumulated_node_count = 0
    saw_node_count = False
    started_at = perf_counter()

    while True:
        base_result = model.base_model.solve(
            options=_remaining_internal_options(options, started_at=started_at),
            objective=objective,
            extra_constraints=tuple(accumulated_constraints),
        )
        if base_result.mip_node_count is not None:
            accumulated_node_count += int(base_result.mip_node_count)
            saw_node_count = True

        callback_result = _base_result_to_callback_result(base_result)
        if not callback_result.success or callback_result.assignment is None:
            return _finalize_loop_result(
                callback_result,
                rejected_incumbent_count=rejected_incumbent_count,
                accumulated_node_count=accumulated_node_count if saw_node_count else None,
            )

        if _assignment_is_connected(model, callback_result.assignment):
            return _finalize_loop_result(
                callback_result,
                rejected_incumbent_count=rejected_incumbent_count,
                accumulated_node_count=accumulated_node_count if saw_node_count else None,
            )

        rejected_incumbent_count += 1
        accumulated_constraints.append(
            _solution_exclusion_constraint(
                model.num_variables,
                callback_result.assignment_variable_values or (),
            )
        )


def solve_callback_parallel_model(
    model: CallbackParallelMilpModel | PuzzleData,
    options: Mapping[str, object] | None = None,
    *,
    objective: Sequence[float] | None = None,
    extra_constraints: Sequence[LinearConstraint] = (),
) -> CallbackParallelSolveResult:
    """Solve the base MILP and reject disconnected incumbents by graph validation."""

    if isinstance(model, PuzzleData):
        model = CallbackParallelMilpModel.from_puzzle_data(model)

    return _solve_internal_base_with_connectivity_rejections(
        model,
        options=_internal_solver_options(options),
        objective=objective,
        extra_constraints=extra_constraints,
    )


__all__ = ["solve_callback_parallel_model"]
