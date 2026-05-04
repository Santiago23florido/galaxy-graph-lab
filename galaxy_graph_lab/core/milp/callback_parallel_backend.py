from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from scipy.optimize import LinearConstraint

from ..model_data import PuzzleData
from .callback_parallel_model import (
    CallbackParallelMilpModel,
    CallbackParallelProblemPayload,
    CallbackParallelSolveResult,
)


@dataclass(slots=True)
class _CallbackProgressState:
    """Mutable progress snapshot populated from the external solver callback."""

    mip_node_count: int | None = None
    best_objective_value: float | None = None
    best_bound: float | None = None


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


def _cplex_linear_rows(
    payload: CallbackParallelProblemPayload,
) -> tuple[list[list[list[int] | list[float]]], str, list[float]]:
    lin_expr: list[list[list[int] | list[float]]] = []
    senses: list[str] = []
    rhs: list[float] = []

    for row in payload.constraint_rows:
        lin_expr.append([list(row.columns), list(row.coefficients)])
        senses.append(row.sense)
        rhs.append(row.rhs)

    return lin_expr, "".join(senses), rhs


def _register_progress_callback(
    cplex_model: Any,
    cplex_module: Any,
) -> _CallbackProgressState:
    progress = _CallbackProgressState()

    callback_namespace = getattr(cplex_module, "callbacks", None)
    mip_info_callback = None if callback_namespace is None else getattr(
        callback_namespace, "MIPInfoCallback", None
    )
    if mip_info_callback is None:
        return progress

    class ProgressCallback(mip_info_callback):
        def __call__(self) -> None:  # pragma: no cover - depends on external backend
            try:
                progress.mip_node_count = int(self.get_num_nodes())
            except Exception:
                pass
            try:
                if self.has_incumbent():
                    progress.best_objective_value = float(
                        self.get_incumbent_objective_value()
                    )
            except Exception:
                pass
            try:
                progress.best_bound = float(self.get_best_objective_value())
            except Exception:
                pass

    cplex_model.register_callback(ProgressCallback)
    return progress


def _extract_solution_details(
    cplex_model: Any,
    progress: _CallbackProgressState,
) -> tuple[bool, int, str, tuple[float, ...] | None, float | None, float | None, int | None]:
    solution = cplex_model.solution
    status = int(solution.get_status())
    message = str(solution.get_status_string())

    values: tuple[float, ...] | None = None
    objective_value: float | None = None
    mip_gap: float | None = None
    mip_node_count: int | None = progress.mip_node_count

    success = False
    try:
        success = bool(solution.is_primal_feasible())
    except Exception:
        success = False

    if success:
        values = tuple(float(value) for value in solution.get_values())
        try:
            objective_value = float(solution.get_objective_value())
        except Exception:
            objective_value = progress.best_objective_value

    try:
        mip_gap = float(solution.MIP.get_mip_relative_gap())
    except Exception:
        mip_gap = None

    if mip_node_count is None:
        try:
            mip_node_count = int(solution.progress.get_num_nodes_processed())
        except Exception:
            mip_node_count = None

    return success, status, message, values, objective_value, mip_gap, mip_node_count


def solve_callback_parallel_model(
    model: CallbackParallelMilpModel | PuzzleData,
    options: Mapping[str, object] | None = None,
    *,
    objective: Sequence[float] | None = None,
    extra_constraints: Sequence[LinearConstraint] = (),
) -> CallbackParallelSolveResult:
    """Solve one exact-flow model instance through an external callback backend."""

    import cplex

    if isinstance(model, PuzzleData):
        model = CallbackParallelMilpModel.from_puzzle_data(model)

    payload = model.build_payload(
        objective=objective,
        extra_constraints=extra_constraints,
    )

    cplex_model = cplex.Cplex()
    cplex_model.objective.set_sense(cplex_model.objective.sense.minimize)
    cplex_model.set_results_stream(None)
    cplex_model.set_log_stream(None)
    cplex_model.set_warning_stream(None)
    cplex_model.set_error_stream(None)

    thread_count = _resolve_thread_count(options)
    if thread_count > 0:
        cplex_model.parameters.threads.set(thread_count)

    time_limit = _resolve_time_limit(options)
    if time_limit is not None:
        cplex_model.parameters.timelimit.set(time_limit)

    mip_gap = _resolve_mip_gap(options)
    if mip_gap is not None:
        cplex_model.parameters.mip.tolerances.mipgap.set(mip_gap)

    cplex_model.variables.add(
        obj=list(payload.objective),
        lb=list(payload.lower_bounds),
        ub=list(payload.upper_bounds),
        types="".join(payload.variable_types),
        names=list(payload.variable_names),
    )

    lin_expr, senses, rhs = _cplex_linear_rows(payload)
    if lin_expr:
        cplex_model.linear_constraints.add(
            lin_expr=lin_expr,
            senses=senses,
            rhs=rhs,
        )

    progress = _register_progress_callback(cplex_model, cplex)
    cplex_model.solve()

    (
        success,
        status,
        message,
        values,
        objective_value,
        mip_gap_value,
        mip_node_count,
    ) = _extract_solution_details(cplex_model, progress)

    return model.result_from_variable_values(
        success=success,
        status=status,
        message=message,
        variable_values=values,
        objective_value=objective_value,
        mip_gap=mip_gap_value,
        mip_node_count=mip_node_count,
    )


__all__ = ["solve_callback_parallel_model"]
