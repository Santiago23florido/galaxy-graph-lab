from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_array, coo_array, hstack

from ..board import Cell
from ..model_data import PuzzleData
from .base_model import BaseMilpModel, GalaxyAssignment, _build_exact_constraint


DirectedFlowKey = tuple[str, Cell, Cell]
SourceFlowKey = tuple[str, Cell]


def _freeze_float_mapping(
    data: dict[DirectedFlowKey, float] | dict[SourceFlowKey, float],
) -> Mapping[object, float]:
    return MappingProxyType(dict(data))


def _build_upper_bound_constraint(
    num_variables: int,
    rows: Sequence[tuple[Sequence[int], Sequence[float], float]],
) -> LinearConstraint | None:
    if not rows:
        return None

    row_indices: list[int] = []
    col_indices: list[int] = []
    data: list[float] = []
    upper_bounds: list[float] = []

    for row_index, (columns, coefficients, upper_bound) in enumerate(rows):
        upper_bounds.append(upper_bound)
        for column, coefficient in zip(columns, coefficients, strict=True):
            row_indices.append(row_index)
            col_indices.append(column)
            data.append(coefficient)

    matrix = coo_array(
        (
            np.asarray(data, dtype=float),
            (
                np.asarray(row_indices, dtype=int),
                np.asarray(col_indices, dtype=int),
            ),
        ),
        shape=(len(rows), num_variables),
    ).tocsc()
    lower_bounds = np.full(len(rows), -np.inf, dtype=float)
    upper_bounds_vector = np.asarray(upper_bounds, dtype=float)
    return LinearConstraint(matrix, lower_bounds, upper_bounds_vector)


def _expand_constraint(
    constraint: LinearConstraint,
    num_extra_variables: int,
) -> LinearConstraint:
    if num_extra_variables == 0:
        return constraint

    matrix = hstack(
        [
            csc_array(constraint.A),
            csc_array((constraint.A.shape[0], num_extra_variables), dtype=float),
        ],
        format="csc",
    )
    return LinearConstraint(
        matrix,
        np.asarray(constraint.lb, dtype=float),
        np.asarray(constraint.ub, dtype=float),
    )


@dataclass(frozen=True, slots=True)
class FlowMilpSolveResult:
    """Structured result of solving the phase-5 exact-flow MILP."""

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


@dataclass(frozen=True, slots=True)
class FlowMilpModel:
    """Exact connectivity MILP with source-rooted flow variables."""

    puzzle_data: PuzzleData
    base_model: BaseMilpModel
    directed_flow_keys: tuple[DirectedFlowKey, ...]
    source_flow_keys: tuple[SourceFlowKey, ...]
    directed_flow_index_by_key: Mapping[DirectedFlowKey, int]
    source_flow_index_by_key: Mapping[SourceFlowKey, int]
    objective: np.ndarray
    integrality: np.ndarray
    bounds: Bounds
    base_constraints: tuple[LinearConstraint, ...]
    edge_tail_capacity_constraints: LinearConstraint | None
    edge_head_capacity_constraints: LinearConstraint | None
    source_capacity_constraints: LinearConstraint | None
    flow_balance_constraints: LinearConstraint | None
    source_supply_constraints: LinearConstraint | None
    constraints: tuple[LinearConstraint, ...]

    @classmethod
    def from_puzzle_data(cls, puzzle_data: PuzzleData) -> "FlowMilpModel":
        """Build the exact flow MILP over one puzzle instance."""

        base_model = BaseMilpModel.from_puzzle_data(puzzle_data)

        directed_flow_keys = tuple(
            (center.id, cell, neighbor)
            for center in puzzle_data.centers
            for cell in puzzle_data.cells
            for neighbor in puzzle_data.neighbors[cell]
        )
        source_flow_keys = tuple(
            (center.id, cell)
            for center in puzzle_data.centers
            for cell in puzzle_data.kernel_by_center[center.id]
        )

        directed_flow_start = base_model.num_variables
        source_flow_start = directed_flow_start + len(directed_flow_keys)

        directed_flow_index_by_key = MappingProxyType(
            {
                key: directed_flow_start + index
                for index, key in enumerate(directed_flow_keys)
            }
        )
        source_flow_index_by_key = MappingProxyType(
            {
                key: source_flow_start + index
                for index, key in enumerate(source_flow_keys)
            }
        )

        num_variables = source_flow_start + len(source_flow_keys)
        num_flow_variables = len(directed_flow_keys) + len(source_flow_keys)

        base_constraints = tuple(
            _expand_constraint(constraint, num_flow_variables)
            for constraint in base_model.constraints
        )

        edge_tail_capacity_rows: list[tuple[Sequence[int], Sequence[float], float]] = []
        edge_head_capacity_rows: list[tuple[Sequence[int], Sequence[float], float]] = []
        for center in puzzle_data.centers:
            flow_capacity = float(len(puzzle_data.admissible_cells_by_center[center.id]))
            for cell in puzzle_data.cells:
                x_index = base_model.variable_index(cell, center.id)
                for neighbor in puzzle_data.neighbors[cell]:
                    flow_index = directed_flow_index_by_key[(center.id, cell, neighbor)]
                    edge_tail_capacity_rows.append(
                        (
                            [flow_index, x_index],
                            [1.0, -flow_capacity],
                            0.0,
                        )
                    )
                    edge_head_capacity_rows.append(
                        (
                            [flow_index, base_model.variable_index(neighbor, center.id)],
                            [1.0, -flow_capacity],
                            0.0,
                        )
                    )

        source_capacity_rows: list[tuple[Sequence[int], Sequence[float], float]] = []
        for center in puzzle_data.centers:
            flow_capacity = float(len(puzzle_data.admissible_cells_by_center[center.id]))
            for cell in puzzle_data.kernel_by_center[center.id]:
                source_capacity_rows.append(
                    (
                        [
                            source_flow_index_by_key[(center.id, cell)],
                            base_model.variable_index(cell, center.id),
                        ],
                        [1.0, -flow_capacity],
                        0.0,
                    )
                )

        flow_balance_rows: list[tuple[Sequence[int], Sequence[float], float]] = []
        for center in puzzle_data.centers:
            for cell in puzzle_data.cells:
                columns: list[int] = []
                coefficients: list[float] = []

                for neighbor in puzzle_data.neighbors[cell]:
                    columns.append(directed_flow_index_by_key[(center.id, neighbor, cell)])
                    coefficients.append(1.0)

                if cell in puzzle_data.kernel_by_center[center.id]:
                    columns.append(source_flow_index_by_key[(center.id, cell)])
                    coefficients.append(1.0)

                for neighbor in puzzle_data.neighbors[cell]:
                    columns.append(directed_flow_index_by_key[(center.id, cell, neighbor)])
                    coefficients.append(-1.0)

                columns.append(base_model.variable_index(cell, center.id))
                coefficients.append(-1.0)
                flow_balance_rows.append((columns, coefficients, 0.0))

        source_supply_rows: list[tuple[Sequence[int], Sequence[float], float]] = []
        for center in puzzle_data.centers:
            columns: list[int] = []
            coefficients: list[float] = []

            for cell in puzzle_data.kernel_by_center[center.id]:
                columns.append(source_flow_index_by_key[(center.id, cell)])
                coefficients.append(1.0)

            for cell in puzzle_data.cells:
                columns.append(base_model.variable_index(cell, center.id))
                coefficients.append(-1.0)

            source_supply_rows.append((columns, coefficients, 0.0))

        edge_tail_capacity_constraints = _build_upper_bound_constraint(
            num_variables,
            edge_tail_capacity_rows,
        )
        edge_head_capacity_constraints = _build_upper_bound_constraint(
            num_variables,
            edge_head_capacity_rows,
        )
        source_capacity_constraints = _build_upper_bound_constraint(
            num_variables,
            source_capacity_rows,
        )
        flow_balance_constraints = _build_exact_constraint(
            num_variables,
            flow_balance_rows,
        )
        source_supply_constraints = _build_exact_constraint(
            num_variables,
            source_supply_rows,
        )

        constraints = base_constraints + tuple(
            constraint
            for constraint in (
                edge_tail_capacity_constraints,
                edge_head_capacity_constraints,
                source_capacity_constraints,
                flow_balance_constraints,
                source_supply_constraints,
            )
            if constraint is not None
        )

        lower_bounds = np.zeros(num_variables, dtype=float)
        upper_bounds = np.concatenate(
            (
                np.ones(base_model.num_variables, dtype=float),
                np.full(num_flow_variables, np.inf, dtype=float),
            )
        )
        integrality = np.concatenate(
            (
                np.ones(base_model.num_variables, dtype=int),
                np.zeros(num_flow_variables, dtype=int),
            )
        )

        return cls(
            puzzle_data=puzzle_data,
            base_model=base_model,
            directed_flow_keys=directed_flow_keys,
            source_flow_keys=source_flow_keys,
            directed_flow_index_by_key=directed_flow_index_by_key,
            source_flow_index_by_key=source_flow_index_by_key,
            objective=np.zeros(num_variables, dtype=float),
            integrality=integrality,
            bounds=Bounds(lower_bounds, upper_bounds),
            base_constraints=base_constraints,
            edge_tail_capacity_constraints=edge_tail_capacity_constraints,
            edge_head_capacity_constraints=edge_head_capacity_constraints,
            source_capacity_constraints=source_capacity_constraints,
            flow_balance_constraints=flow_balance_constraints,
            source_supply_constraints=source_supply_constraints,
            constraints=constraints,
        )

    @property
    def num_variables(self) -> int:
        return len(self.objective)

    @property
    def num_assignment_variables(self) -> int:
        return self.base_model.num_variables

    @property
    def num_directed_flow_variables(self) -> int:
        return len(self.directed_flow_keys)

    @property
    def num_source_flow_variables(self) -> int:
        return len(self.source_flow_keys)

    @property
    def edge_tail_capacity_row_count(self) -> int:
        if self.edge_tail_capacity_constraints is None:
            return 0
        return self.edge_tail_capacity_constraints.A.shape[0]

    @property
    def edge_head_capacity_row_count(self) -> int:
        if self.edge_head_capacity_constraints is None:
            return 0
        return self.edge_head_capacity_constraints.A.shape[0]

    @property
    def source_capacity_row_count(self) -> int:
        if self.source_capacity_constraints is None:
            return 0
        return self.source_capacity_constraints.A.shape[0]

    @property
    def flow_balance_row_count(self) -> int:
        if self.flow_balance_constraints is None:
            return 0
        return self.flow_balance_constraints.A.shape[0]

    @property
    def source_supply_row_count(self) -> int:
        if self.source_supply_constraints is None:
            return 0
        return self.source_supply_constraints.A.shape[0]

    def assignment_variable_index(self, cell: Cell, center_id: str) -> int:
        """Return the canonical global index of x[u, g]."""

        return self.base_model.variable_index(cell, center_id)

    def directed_flow_variable_index(
        self,
        center_id: str,
        tail: Cell,
        head: Cell,
    ) -> int:
        """Return the canonical global index of one directed grid-flow variable."""

        key = (center_id, tail, head)
        if key not in self.directed_flow_index_by_key:
            raise ValueError(f"Unknown directed flow variable: {key}")
        return self.directed_flow_index_by_key[key]

    def source_flow_variable_index(self, center_id: str, cell: Cell) -> int:
        """Return the canonical global index of one source-to-kernel flow variable."""

        key = (center_id, cell)
        if key not in self.source_flow_index_by_key:
            raise ValueError(f"Unknown source flow variable: {key}")
        return self.source_flow_index_by_key[key]

    def decode_assignment(self, variable_values: Sequence[float]) -> GalaxyAssignment:
        """Decode the assignment slice of one full flow-model vector."""

        if len(variable_values) != self.num_variables:
            raise ValueError("Variable vector length does not match the flow model.")

        return self.base_model.decode_assignment(
            variable_values[: self.base_model.num_variables]
        )

    def solve(
        self,
        options: Mapping[str, object] | None = None,
    ) -> FlowMilpSolveResult:
        """Solve the exact flow MILP as a feasibility problem with zero objective."""

        result = milp(
            c=self.objective,
            integrality=self.integrality,
            bounds=self.bounds,
            constraints=self.constraints,
            options=None if options is None else dict(options),
        )

        assignment: GalaxyAssignment | None = None
        assignment_variable_values: tuple[float, ...] | None = None
        directed_flow_values: Mapping[DirectedFlowKey, float] | None = None
        source_flow_values: Mapping[SourceFlowKey, float] | None = None
        objective_value: float | None = None
        mip_gap: float | None = None
        mip_node_count: int | None = None

        if getattr(result, "fun", None) is not None:
            objective_value = float(result.fun)
        if getattr(result, "mip_gap", None) is not None:
            mip_gap = float(result.mip_gap)
        if getattr(result, "mip_node_count", None) is not None:
            mip_node_count = int(result.mip_node_count)

        if getattr(result, "x", None) is not None:
            variable_values = tuple(float(value) for value in result.x)
            assignment_variable_values = variable_values[: self.base_model.num_variables]
            directed_flow_values = _freeze_float_mapping(
                {
                    key: variable_values[index]
                    for key, index in self.directed_flow_index_by_key.items()
                }
            )
            source_flow_values = _freeze_float_mapping(
                {
                    key: variable_values[index]
                    for key, index in self.source_flow_index_by_key.items()
                }
            )
            if result.success:
                assignment = self.base_model.decode_assignment(assignment_variable_values)

        return FlowMilpSolveResult(
            success=bool(result.success),
            status=int(result.status),
            message=str(result.message),
            objective_value=objective_value,
            mip_gap=mip_gap,
            mip_node_count=mip_node_count,
            assignment=assignment,
            assignment_variable_values=assignment_variable_values,
            directed_flow_values=directed_flow_values,
            source_flow_values=source_flow_values,
        )


def solve_flow_model(
    puzzle_data: PuzzleData,
    options: Mapping[str, object] | None = None,
) -> FlowMilpSolveResult:
    """Build and solve the phase-5 exact flow MILP for one puzzle instance."""

    model = FlowMilpModel.from_puzzle_data(puzzle_data)
    return model.solve(options=options)


__all__ = [
    "DirectedFlowKey",
    "FlowMilpModel",
    "FlowMilpSolveResult",
    "SourceFlowKey",
    "solve_flow_model",
]
