from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .board import Cell
from .model_data import PuzzleData


CandidateAssignment = Mapping[str, Iterable[Cell]]


@dataclass(frozen=True, slots=True)
class AssignmentValidationResult:
    """Validation flags for a candidate center-to-cells assignment."""

    partition_ok: bool
    admissibility_ok: bool
    symmetry_ok: bool
    kernel_ok: bool
    connectivity_ok: bool

    @property
    def is_valid(self) -> bool:
        return (
            self.partition_ok
            and self.admissibility_ok
            and self.symmetry_ok
            and self.kernel_ok
            and self.connectivity_ok
        )


@dataclass(frozen=True, slots=True)
class _PreparedAssignment:
    cells_by_center: dict[str, frozenset[Cell]]
    has_unknown_center_ids: bool
    has_unknown_cells: bool

    @property
    def is_well_formed(self) -> bool:
        return not self.has_unknown_center_ids and not self.has_unknown_cells


def _prepare_assignment(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> _PreparedAssignment:
    board_cell_set = set(puzzle_data.cells)
    known_center_ids = set(puzzle_data.center_by_id)
    cells_by_center: dict[str, frozenset[Cell]] = {}
    has_unknown_cells = False

    for center in puzzle_data.centers:
        assigned_cells = frozenset(assignment.get(center.id, ()))
        if any(cell not in board_cell_set for cell in assigned_cells):
            has_unknown_cells = True
        cells_by_center[center.id] = assigned_cells

    extra_center_ids = set(assignment).difference(known_center_ids)
    for center_id in extra_center_ids:
        assigned_cells = frozenset(assignment[center_id])
        if any(cell not in board_cell_set for cell in assigned_cells):
            has_unknown_cells = True

    return _PreparedAssignment(
        cells_by_center=cells_by_center,
        has_unknown_center_ids=bool(extra_center_ids),
        has_unknown_cells=has_unknown_cells,
    )


def partition_is_valid(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> bool:
    """Return whether the assignment is an exact partition of the board."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    if not prepared.is_well_formed:
        return False

    assigned_cells: set[Cell] = set()

    for cells in prepared.cells_by_center.values():
        if assigned_cells.intersection(cells):
            return False
        assigned_cells.update(cells)

    return assigned_cells == set(puzzle_data.cells)


def admissibility_is_valid(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> bool:
    """Return whether every assigned cell stays inside its admissible domain."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    if not prepared.is_well_formed:
        return False

    for center in puzzle_data.centers:
        admissible_cells = set(puzzle_data.admissible_cells_by_center[center.id])
        if not prepared.cells_by_center[center.id].issubset(admissible_cells):
            return False

    return True


def symmetry_is_valid(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> bool:
    """Return whether every assigned region is closed under 180-degree rotation."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    if not prepared.is_well_formed:
        return False

    for center in puzzle_data.centers:
        assigned_cells = prepared.cells_by_center[center.id]
        twin_lookup = puzzle_data.twin_by_center_and_cell[center.id]

        for cell in assigned_cells:
            twin = twin_lookup.get(cell)
            if twin is None or twin not in assigned_cells:
                return False

    return True


def kernel_is_valid(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> bool:
    """Return whether every assigned region contains its mandatory kernel."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    if not prepared.is_well_formed:
        return False

    for center in puzzle_data.centers:
        kernel_cells = set(puzzle_data.kernel_by_center[center.id])
        if not kernel_cells.issubset(prepared.cells_by_center[center.id]):
            return False

    return True


def connectivity_is_valid(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> bool:
    """Return whether every assigned region induces a connected subgraph."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    if not prepared.is_well_formed:
        return False

    for center in puzzle_data.centers:
        if not puzzle_data.graph.is_connected(prepared.cells_by_center[center.id]):
            return False

    return True


def validate_assignment(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> AssignmentValidationResult:
    """Run all structural validators on one candidate assignment."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    if not prepared.is_well_formed:
        return AssignmentValidationResult(
            partition_ok=False,
            admissibility_ok=False,
            symmetry_ok=False,
            kernel_ok=False,
            connectivity_ok=False,
        )

    assigned_cells: set[Cell] = set()
    partition_ok = True
    for cells in prepared.cells_by_center.values():
        if assigned_cells.intersection(cells):
            partition_ok = False
            break
        assigned_cells.update(cells)

    if partition_ok:
        partition_ok = assigned_cells == set(puzzle_data.cells)

    admissibility_ok = True
    symmetry_ok = True
    kernel_ok = True
    connectivity_ok = True

    for center in puzzle_data.centers:
        center_id = center.id
        assigned_cells_for_center = prepared.cells_by_center[center_id]
        admissible_cells = set(puzzle_data.admissible_cells_by_center[center_id])
        twin_lookup = puzzle_data.twin_by_center_and_cell[center_id]
        kernel_cells = set(puzzle_data.kernel_by_center[center_id])

        if admissibility_ok and not assigned_cells_for_center.issubset(admissible_cells):
            admissibility_ok = False

        if symmetry_ok:
            for cell in assigned_cells_for_center:
                twin = twin_lookup.get(cell)
                if twin is None or twin not in assigned_cells_for_center:
                    symmetry_ok = False
                    break

        if kernel_ok and not kernel_cells.issubset(assigned_cells_for_center):
            kernel_ok = False

        if connectivity_ok and not puzzle_data.graph.is_connected(
            assigned_cells_for_center
        ):
            connectivity_ok = False

    return AssignmentValidationResult(
        partition_ok=partition_ok,
        admissibility_ok=admissibility_ok,
        symmetry_ok=symmetry_ok,
        kernel_ok=kernel_ok,
        connectivity_ok=connectivity_ok,
    )


__all__ = [
    "AssignmentValidationResult",
    "CandidateAssignment",
    "admissibility_is_valid",
    "connectivity_is_valid",
    "kernel_is_valid",
    "partition_is_valid",
    "symmetry_is_valid",
    "validate_assignment",
]
