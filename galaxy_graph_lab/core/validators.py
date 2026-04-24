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


def _partition_is_valid(
    puzzle_data: PuzzleData,
    prepared: _PreparedAssignment,
) -> bool:
    if not prepared.is_well_formed:
        return False

    assigned_cells: set[Cell] = set()

    for cells in prepared.cells_by_center.values():
        if assigned_cells.intersection(cells):
            return False
        assigned_cells.update(cells)

    return assigned_cells == set(puzzle_data.cells)


def _admissibility_is_valid(
    puzzle_data: PuzzleData,
    prepared: _PreparedAssignment,
) -> bool:
    if not prepared.is_well_formed:
        return False

    for center in puzzle_data.centers:
        admissible_cells = set(puzzle_data.admissible_cells_by_center[center.id])
        if not prepared.cells_by_center[center.id].issubset(admissible_cells):
            return False

    return True


def _symmetry_is_valid(
    puzzle_data: PuzzleData,
    prepared: _PreparedAssignment,
) -> bool:
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


def _kernel_is_valid(
    puzzle_data: PuzzleData,
    prepared: _PreparedAssignment,
) -> bool:
    if not prepared.is_well_formed:
        return False

    for center in puzzle_data.centers:
        kernel_cells = set(puzzle_data.kernel_by_center[center.id])
        if not kernel_cells.issubset(prepared.cells_by_center[center.id]):
            return False

    return True


def _connectivity_is_valid(
    puzzle_data: PuzzleData,
    prepared: _PreparedAssignment,
) -> bool:
    if not prepared.is_well_formed:
        return False

    for center in puzzle_data.centers:
        if not puzzle_data.graph.is_connected(prepared.cells_by_center[center.id]):
            return False

    return True


def partition_is_valid(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> bool:
    """Return whether the assignment is an exact partition of the board."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    return _partition_is_valid(puzzle_data, prepared)


def admissibility_is_valid(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> bool:
    """Return whether every assigned cell stays inside its admissible domain."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    return _admissibility_is_valid(puzzle_data, prepared)


def symmetry_is_valid(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> bool:
    """Return whether every assigned region is closed under 180-degree rotation."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    return _symmetry_is_valid(puzzle_data, prepared)


def kernel_is_valid(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> bool:
    """Return whether every assigned region contains its mandatory kernel."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    return _kernel_is_valid(puzzle_data, prepared)


def connectivity_is_valid(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> bool:
    """Return whether every assigned region induces a connected subgraph."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    return _connectivity_is_valid(puzzle_data, prepared)


def validate_assignment(
    puzzle_data: PuzzleData,
    assignment: CandidateAssignment,
) -> AssignmentValidationResult:
    """Run all structural Phase 3 validators on one candidate assignment."""

    prepared = _prepare_assignment(puzzle_data, assignment)
    return AssignmentValidationResult(
        partition_ok=_partition_is_valid(puzzle_data, prepared),
        admissibility_ok=_admissibility_is_valid(puzzle_data, prepared),
        symmetry_ok=_symmetry_is_valid(puzzle_data, prepared),
        kernel_ok=_kernel_is_valid(puzzle_data, prepared),
        connectivity_ok=_connectivity_is_valid(puzzle_data, prepared),
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
