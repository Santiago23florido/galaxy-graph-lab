from __future__ import annotations

from .board import BoardSpec, Cell
from .centers import CenterSpec


def tau(center: CenterSpec, cell: Cell) -> tuple[int, int]:
    """Apply the 180-degree rotation map on cell coordinates."""

    return center.row_coord2 - cell.row, center.col_coord2 - cell.col


def twin_cell(board: BoardSpec, center: CenterSpec, cell: Cell) -> Cell | None:
    """Return the rotated twin when it stays inside the board."""

    twin_row, twin_col = tau(center=center, cell=cell)

    if not board.contains_indices(twin_row, twin_col):
        return None

    return Cell(row=twin_row, col=twin_col)


def is_admissible_cell(board: BoardSpec, center: CenterSpec, cell: Cell) -> bool:
    """Return whether the cell belongs to the admissible domain U_g."""

    return twin_cell(board=board, center=center, cell=cell) is not None


def admissible_cells(board: BoardSpec, center: CenterSpec) -> tuple[Cell, ...]:

    return tuple(
        cell for cell in board.iter_cells() if is_admissible_cell(board, center, cell)
    )


def is_kernel_cell(center: CenterSpec, cell: Cell) -> bool:
    """Return whether the center is incident to the cell."""

    return (
        abs((2 * cell.row) - center.row_coord2) <= 1
        and abs((2 * cell.col) - center.col_coord2) <= 1
    )


def kernel_cells(board: BoardSpec, center: CenterSpec) -> tuple[Cell, ...]:
    """Return the mandatory kernel cells for the given center."""

    return tuple(cell for cell in board.iter_cells() if is_kernel_cell(center, cell))


def twin_map(board: BoardSpec, center: CenterSpec) -> dict[Cell, Cell]:
    """Return the valid twin lookup for one center."""

    mapping: dict[Cell, Cell] = {}

    for cell in board.iter_cells():
        twin = twin_cell(board=board, center=center, cell=cell)
        if twin is not None:
            mapping[cell] = twin

    return mapping


__all__ = [
    "admissible_cells",
    "is_admissible_cell",
    "is_kernel_cell",
    "kernel_cells",
    "tau",
    "twin_cell",
    "twin_map",
]
