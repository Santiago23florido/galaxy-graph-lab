from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array

from ..board import Cell
from ..model_data import PuzzleData


AssignmentVariableKey = tuple[Cell, str]


def _freeze_center_cell_mapping(
    data: dict[str, list[Cell] | tuple[Cell, ...]],
) -> Mapping[str, tuple[Cell, ...]]:
    return MappingProxyType(
        {
            center_id: tuple(cells)
            for center_id, cells in data.items()
        }
    )


def _freeze_cell_center_mapping(
    data: dict[Cell, str],
) -> Mapping[Cell, str]:
    return MappingProxyType(dict(data))


def _build_exact_constraint(
    num_variables: int,
    rows: Sequence[tuple[Sequence[int], Sequence[float], float]],
) -> LinearConstraint | None:
    if not rows:
        return None

    # Convert row-wise equalities into one sparse matrix A with exact bounds
    # so this becomes A x = b for SciPy's MILP interface.
    row_indices: list[int] = []
    col_indices: list[int] = []
    data: list[float] = []
    rhs: list[float] = []

    for row_index, (columns, coefficients, target_value) in enumerate(rows):
        rhs.append(target_value)
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
    rhs_vector = np.asarray(rhs, dtype=float)
    return LinearConstraint(matrix, rhs_vector, rhs_vector)


@dataclass(frozen=True, slots=True)
class GalaxyAssignment:
    """Structured assignment decoded from solver variables."""

    assigned_center_by_cell: Mapping[Cell, str]
    cells_by_center: Mapping[str, tuple[Cell, ...]]


@dataclass(frozen=True, slots=True)
class BaseMilpSolveResult:
    """Structured result of solving the phase-4 base MILP."""

    success: bool
    status: int
    message: str
    objective_value: float | None
    mip_gap: float | None
    mip_node_count: int | None
    assignment: GalaxyAssignment | None
    variable_values: tuple[float, ...] | None


@dataclass(frozen=True, slots=True)
class BaseMilpModel:
    """Base binary assignment model without connectivity constraints."""

    puzzle_data: PuzzleData
    variable_keys: tuple[AssignmentVariableKey, ...]
    variable_index_by_key: Mapping[AssignmentVariableKey, int]
    objective: np.ndarray
    integrality: np.ndarray
    bounds: Bounds
    partition_constraints: LinearConstraint
    inadmissibility_constraints: LinearConstraint | None
    symmetry_constraints: LinearConstraint | None
    kernel_constraints: LinearConstraint | None
    constraints: tuple[LinearConstraint, ...]

    @classmethod
    def from_puzzle_data(cls, puzzle_data: PuzzleData) -> "BaseMilpModel":
        """Build the base MILP over one puzzle instance."""

        # Fix one canonical order for x[u, g] so constraint building and
        # solution decoding both use the same indexing layer.
        variable_keys = tuple(
            (cell, center.id)
            for cell in puzzle_data.cells
            for center in puzzle_data.centers
        )
        variable_index_by_key = MappingProxyType(
            {
                key: index
                for index, key in enumerate(variable_keys)
            }
        )
        num_variables = len(variable_keys)

        # Partition: each cell must choose exactly one center.
        partition_rows: list[tuple[Sequence[int], Sequence[float], float]] = []
        for cell in puzzle_data.cells:
            columns = [
                variable_index_by_key[(cell, center.id)]
                for center in puzzle_data.centers
            ]
            coefficients = [1.0] * len(columns)
            partition_rows.append((columns, coefficients, 1.0))

        # If u is not in U_g, force x[u, g] = 0 with a one-variable equality.
        # For now the variable stays in the model and is just fixed.
        inadmissibility_rows: list[tuple[Sequence[int], Sequence[float], float]] = []
        for center in puzzle_data.centers:
            admissible_cells = set(puzzle_data.admissible_cells_by_center[center.id])
            for cell in puzzle_data.cells:
                if cell in admissible_cells:
                    continue
                inadmissibility_rows.append(
                    (
                        [variable_index_by_key[(cell, center.id)]],
                        [1.0],
                        0.0,
                    )
                )

        # Symmetry: x[u, g] - x[tau_g(u), g] = 0. Only add one equation per
        # pair so the same equality is not duplicated in reverse.
        symmetry_rows: list[tuple[Sequence[int], Sequence[float], float]] = []
        for center in puzzle_data.centers:
            twin_lookup = puzzle_data.twin_by_center_and_cell[center.id]
            for cell in puzzle_data.admissible_cells_by_center[center.id]:
                twin = twin_lookup[cell]
                if cell >= twin:
                    continue
                symmetry_rows.append(
                    (
                        [
                            variable_index_by_key[(cell, center.id)],
                            variable_index_by_key[(twin, center.id)],
                        ],
                        [1.0, -1.0],
                        0.0,
                    )
                )

        # Kernel cells are mandatory for their center, so fix x[u, g] = 1.
        kernel_rows: list[tuple[Sequence[int], Sequence[float], float]] = []
        for center in puzzle_data.centers:
            for cell in puzzle_data.kernel_by_center[center.id]:
                kernel_rows.append(
                    (
                        [variable_index_by_key[(cell, center.id)]],
                        [1.0],
                        1.0,
                    )
                )

        partition_constraints = _build_exact_constraint(num_variables, partition_rows)
        if partition_constraints is None:
            raise ValueError("Base MILP requires at least one partition constraint.")

        # Keep each constraint family separate because the row counts are
        # useful for inspection and debugging by block.
        inadmissibility_constraints = _build_exact_constraint(
            num_variables,
            inadmissibility_rows,
        )
        symmetry_constraints = _build_exact_constraint(num_variables, symmetry_rows)
        kernel_constraints = _build_exact_constraint(num_variables, kernel_rows)

        constraints = tuple(
            constraint
            for constraint in (
                partition_constraints,
                inadmissibility_constraints,
                symmetry_constraints,
                kernel_constraints,
            )
            if constraint is not None
        )

        return cls(
            puzzle_data=puzzle_data,
            variable_keys=variable_keys,
            variable_index_by_key=variable_index_by_key,
            objective=np.zeros(num_variables, dtype=float),
            integrality=np.ones(num_variables, dtype=int),
            bounds=Bounds(
                np.zeros(num_variables, dtype=float),
                np.ones(num_variables, dtype=float),
            ),
            partition_constraints=partition_constraints,
            inadmissibility_constraints=inadmissibility_constraints,
            symmetry_constraints=symmetry_constraints,
            kernel_constraints=kernel_constraints,
            constraints=constraints,
        )

    @property
    def num_variables(self) -> int:
        return len(self.variable_keys)

    @property
    def partition_row_count(self) -> int:
        return self.partition_constraints.A.shape[0]

    @property
    def inadmissibility_row_count(self) -> int:
        if self.inadmissibility_constraints is None:
            return 0
        return self.inadmissibility_constraints.A.shape[0]

    @property
    def symmetry_row_count(self) -> int:
        if self.symmetry_constraints is None:
            return 0
        return self.symmetry_constraints.A.shape[0]

    @property
    def kernel_row_count(self) -> int:
        if self.kernel_constraints is None:
            return 0
        return self.kernel_constraints.A.shape[0]

    def variable_index(self, cell: Cell, center_id: str) -> int:
        """Return the canonical solver index of one assignment variable."""

        key = (cell, center_id)
        if key not in self.variable_index_by_key:
            raise ValueError(f"Unknown assignment variable: {key}")
        return self.variable_index_by_key[key]

    def decode_assignment(self, variable_values: Sequence[float]) -> GalaxyAssignment:
        """Decode one solver vector into the canonical assignment structure."""

        if len(variable_values) != len(self.variable_keys):
            raise ValueError("Variable vector length does not match the model.")

        # This phase expects binary values, but use a 0.5 threshold to absorb
        # small numerical noise from the solver output.
        selected_centers_by_cell: dict[Cell, list[str]] = {
            cell: []
            for cell in self.puzzle_data.cells
        }
        cells_by_center_lists: dict[str, list[Cell]] = {
            center.id: []
            for center in self.puzzle_data.centers
        }

        for value, (cell, center_id) in zip(variable_values, self.variable_keys, strict=True):
            if value < 0.5:
                continue
            selected_centers_by_cell[cell].append(center_id)
            cells_by_center_lists[center_id].append(cell)

        assigned_center_by_cell: dict[Cell, str] = {}
        for cell in self.puzzle_data.cells:
            selected_centers = selected_centers_by_cell[cell]
            if len(selected_centers) != 1:
                raise ValueError(
                    f"Expected exactly one selected center for {cell}, got {selected_centers}."
                )
            assigned_center_by_cell[cell] = selected_centers[0]

        return GalaxyAssignment(
            assigned_center_by_cell=_freeze_cell_center_mapping(assigned_center_by_cell),
            cells_by_center=_freeze_center_cell_mapping(cells_by_center_lists),
        )

    def solve(
        self,
        options: Mapping[str, object] | None = None,
    ) -> BaseMilpSolveResult:
        """Solve the base MILP as a feasibility problem with zero objective."""

        # The objective is zero because this phase is only a feasibility
        # model. Connectivity and stronger structure come later.
        result = milp(
            c=self.objective,
            integrality=self.integrality,
            bounds=self.bounds,
            constraints=self.constraints,
            options=None if options is None else dict(options),
        )

        variable_values: tuple[float, ...] | None = None
        assignment: GalaxyAssignment | None = None
        objective_value: float | None = None
        mip_gap: float | None = None
        mip_node_count: int | None = None

        if getattr(result, "x", None) is not None:
            variable_values = tuple(float(value) for value in result.x)
        if getattr(result, "fun", None) is not None:
            objective_value = float(result.fun)
        if getattr(result, "mip_gap", None) is not None:
            mip_gap = float(result.mip_gap)
        if getattr(result, "mip_node_count", None) is not None:
            mip_node_count = int(result.mip_node_count)
        if result.success and variable_values is not None:
            assignment = self.decode_assignment(variable_values)

        return BaseMilpSolveResult(
            success=bool(result.success),
            status=int(result.status),
            message=str(result.message),
            objective_value=objective_value,
            mip_gap=mip_gap,
            mip_node_count=mip_node_count,
            assignment=assignment,
            variable_values=variable_values,
        )


def solve_base_model(
    puzzle_data: PuzzleData,
    options: Mapping[str, object] | None = None,
) -> BaseMilpSolveResult:
    """Build and solve the phase-4 base MILP for one puzzle instance."""

    model = BaseMilpModel.from_puzzle_data(puzzle_data)
    return model.solve(options=options)


__all__ = [
    "AssignmentVariableKey",
    "BaseMilpModel",
    "BaseMilpSolveResult",
    "GalaxyAssignment",
    "solve_base_model",
]
