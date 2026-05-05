from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from scipy.optimize import LinearConstraint
from scipy.sparse import csc_array

from ..board import Cell
from ..model_data import PuzzleData
from .base_model import BaseMilpModel, GalaxyAssignment


DirectedFlowKey = tuple[str, Cell, Cell]
SourceFlowKey = tuple[str, Cell]


@dataclass(frozen=True, slots=True)
class CallbackParallelConstraintRow:
    """One linear row encoded for an external callback-capable MILP backend."""

    columns: tuple[int, ...]
    coefficients: tuple[float, ...]
    sense: str
    rhs: float


@dataclass(frozen=True, slots=True)
class CallbackParallelProblemPayload:
    """Solver-neutral payload exported from the callback-parallel model layer."""

    objective: tuple[float, ...]
    lower_bounds: tuple[float, ...]
    upper_bounds: tuple[float, ...]
    variable_types: tuple[str, ...]
    variable_names: tuple[str, ...]
    constraint_rows: tuple[CallbackParallelConstraintRow, ...]


@dataclass(frozen=True, slots=True)
class CallbackParallelSolveResult:
    """Structured result of solving the callback-parallel exact MILP."""

    success: bool
    status: int
    message: str
    objective_value: float | None
    mip_gap: float | None
    mip_node_count: int | None
    assignment: GalaxyAssignment | None
    assignment_variable_values: tuple[float, ...] | None
    directed_flow_values: Mapping[DirectedFlowKey, float] | None
    source_flow_values: Mapping[SourceFlowKey, float] | None


def _freeze_float_mapping(
    data: dict[DirectedFlowKey, float] | dict[SourceFlowKey, float],
) -> Mapping[object, float]:
    return MappingProxyType(dict(data))


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _constraint_to_rows(
    constraint: LinearConstraint,
) -> tuple[CallbackParallelConstraintRow, ...]:
    """Expand one SciPy LinearConstraint into external-solver row records."""

    matrix = csc_array(constraint.A).tocsr()
    rows: list[CallbackParallelConstraintRow] = []
    lower_bounds = np.asarray(constraint.lb, dtype=float)
    upper_bounds = np.asarray(constraint.ub, dtype=float)

    for row_index in range(matrix.shape[0]):
        row = matrix.getrow(row_index)
        columns = tuple(int(index) for index in row.indices.tolist())
        coefficients = tuple(float(value) for value in row.data.tolist())
        lower_bound = float(lower_bounds[row_index])
        upper_bound = float(upper_bounds[row_index])

        if np.isneginf(lower_bound) and np.isposinf(upper_bound):
            continue
        if np.isfinite(lower_bound) and np.isfinite(upper_bound):
            if np.isclose(lower_bound, upper_bound):
                rows.append(
                    CallbackParallelConstraintRow(
                        columns=columns,
                        coefficients=coefficients,
                        sense="E",
                        rhs=lower_bound,
                    )
                )
            else:
                rows.append(
                    CallbackParallelConstraintRow(
                        columns=columns,
                        coefficients=coefficients,
                        sense="G",
                        rhs=lower_bound,
                    )
                )
                rows.append(
                    CallbackParallelConstraintRow(
                        columns=columns,
                        coefficients=coefficients,
                        sense="L",
                        rhs=upper_bound,
                    )
                )
            continue
        if np.isfinite(upper_bound):
            rows.append(
                CallbackParallelConstraintRow(
                    columns=columns,
                    coefficients=coefficients,
                    sense="L",
                    rhs=upper_bound,
                )
            )
            continue
        if np.isfinite(lower_bound):
            rows.append(
                CallbackParallelConstraintRow(
                    columns=columns,
                    coefficients=coefficients,
                    sense="G",
                    rhs=lower_bound,
                )
            )

    return tuple(rows)


@dataclass(frozen=True, slots=True)
class CallbackParallelMilpModel:
    """Base MILP exported in a backend-neutral form for callback solvers."""

    puzzle_data: PuzzleData
    base_model: BaseMilpModel

    @classmethod
    def from_puzzle_data(cls, puzzle_data: PuzzleData) -> "CallbackParallelMilpModel":
        return cls(
            puzzle_data=puzzle_data,
            base_model=BaseMilpModel.from_puzzle_data(puzzle_data),
        )

    @property
    def num_variables(self) -> int:
        return self.base_model.num_variables

    @property
    def num_assignment_variables(self) -> int:
        return self.base_model.num_variables

    @property
    def directed_flow_keys(self) -> tuple[DirectedFlowKey, ...]:
        return tuple()

    @property
    def source_flow_keys(self) -> tuple[SourceFlowKey, ...]:
        return tuple()

    @property
    def directed_flow_index_by_key(self) -> Mapping[DirectedFlowKey, int]:
        return MappingProxyType({})

    @property
    def source_flow_index_by_key(self) -> Mapping[SourceFlowKey, int]:
        return MappingProxyType({})

    def assignment_variable_index(self, cell: Cell, center_id: str) -> int:
        return self.base_model.variable_index(cell, center_id)

    def decode_assignment(self, variable_values: Sequence[float]) -> GalaxyAssignment:
        return self.base_model.decode_assignment(variable_values)

    def _variable_names(self) -> tuple[str, ...]:
        assignment_names = tuple(
            f"x__r{cell.row}_c{cell.col}__{center_id}"
            for cell, center_id in self.base_model.variable_keys
        )
        return assignment_names

    def build_payload(
        self,
        *,
        objective: Sequence[float] | None = None,
        extra_constraints: Sequence[LinearConstraint] = (),
    ) -> CallbackParallelProblemPayload:
        """Export the base MILP into a solver-neutral row payload."""

        objective_vector = self.base_model.objective
        if objective is not None:
            objective_vector = np.asarray(objective, dtype=float)
            if objective_vector.shape != (self.num_variables,):
                raise ValueError(
                    "Custom objective length does not match the callback-parallel model."
                )

        constraints = self.base_model.constraints + tuple(extra_constraints)
        constraint_rows: list[CallbackParallelConstraintRow] = []
        for constraint in constraints:
            constraint_rows.extend(_constraint_to_rows(constraint))

        lower_bounds = np.asarray(self.base_model.bounds.lb, dtype=float)
        upper_bounds = np.asarray(self.base_model.bounds.ub, dtype=float)
        integrality = np.asarray(self.base_model.integrality, dtype=int)
        variable_types = tuple(
            "B" if int(value) == 1 else "C"
            for value in integrality.tolist()
        )

        return CallbackParallelProblemPayload(
            objective=tuple(float(value) for value in objective_vector.tolist()),
            lower_bounds=tuple(float(value) for value in lower_bounds.tolist()),
            upper_bounds=tuple(float(value) for value in upper_bounds.tolist()),
            variable_types=variable_types,
            variable_names=self._variable_names(),
            constraint_rows=tuple(constraint_rows),
        )

    def result_from_variable_values(
        self,
        *,
        success: bool,
        status: int,
        message: str,
        variable_values: Sequence[float] | None,
        objective_value: float | None,
        mip_gap: float | None,
        mip_node_count: int | None,
    ) -> CallbackParallelSolveResult:
        """Decode one backend solution vector into the shared structured result."""

        assignment: GalaxyAssignment | None = None
        assignment_variable_values: tuple[float, ...] | None = None
        directed_flow_values: Mapping[DirectedFlowKey, float] | None = None
        source_flow_values: Mapping[SourceFlowKey, float] | None = None

        if variable_values is not None:
            values = tuple(float(value) for value in variable_values)
            if len(values) != self.num_variables:
                raise ValueError(
                    "Callback backend returned a solution vector with the wrong size."
                )
            assignment_variable_values = values[: self.num_assignment_variables]
            directed_flow_values = _freeze_float_mapping(
                {
                    key: values[index]
                    for key, index in self.directed_flow_index_by_key.items()
                }
            )
            source_flow_values = _freeze_float_mapping(
                {
                    key: values[index]
                    for key, index in self.source_flow_index_by_key.items()
                }
            )
            if success:
                assignment = self.base_model.decode_assignment(assignment_variable_values)

        return CallbackParallelSolveResult(
            success=bool(success),
            status=int(status),
            message=str(message),
            objective_value=_float_or_none(objective_value),
            mip_gap=_float_or_none(mip_gap),
            mip_node_count=_int_or_none(mip_node_count),
            assignment=assignment,
            assignment_variable_values=assignment_variable_values,
            directed_flow_values=directed_flow_values,
            source_flow_values=source_flow_values,
        )

    def solve(
        self,
        options: Mapping[str, object] | None = None,
        *,
        objective: Sequence[float] | None = None,
        extra_constraints: Sequence[LinearConstraint] = (),
    ) -> CallbackParallelSolveResult:
        """Solve the model through the callback-parallel backend adapter."""

        from .callback_parallel_backend import solve_callback_parallel_model

        return solve_callback_parallel_model(
            self,
            options=options,
            objective=objective,
            extra_constraints=extra_constraints,
        )


__all__ = [
    "CallbackParallelConstraintRow",
    "CallbackParallelMilpModel",
    "CallbackParallelProblemPayload",
    "CallbackParallelSolveResult",
]
