from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True, order=True)
class Cell:
    """A board cell identified by zero-based coordinates."""

    row: int
    col: int

    def __post_init__(self) -> None:
        if not _is_plain_int(self.row) or not _is_plain_int(self.col):
            raise TypeError("Cell coordinates must be integers.")
        if self.row < 0 or self.col < 0:
            raise ValueError("Cell coordinates must be non-negative.")


@dataclass(frozen=True, slots=True)
class BoardSpec:
    """Immutable board dimensions and canonical cell ordering."""

    rows: int
    cols: int

    def __post_init__(self) -> None:
        if not _is_plain_int(self.rows) or not _is_plain_int(self.cols):
            raise TypeError("Board dimensions must be integers.")
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("Board dimensions must be positive.")

    def contains(self, cell: Cell) -> bool:

        return self.contains_indices(cell.row, cell.col)

    def contains_indices(self, row: int, col: int) -> bool:

        return 0 <= row < self.rows and 0 <= col < self.cols

    def iter_cells(self) -> Iterator[Cell]:

        for row in range(self.rows):
            for col in range(self.cols):
                yield Cell(row=row, col=col)

    def cells(self) -> tuple[Cell, ...]:

        return tuple(self.iter_cells())


__all__ = ["BoardSpec", "Cell"]
