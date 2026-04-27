from __future__ import annotations

from types import MappingProxyType

from ..board import BoardSpec, Cell
from ..geometry import kernel_cells
from .center_placement import PlacedCenterRegion


def _grow_one_rectangular_region(
    board: BoardSpec,
    region: PlacedCenterRegion,
) -> tuple[Cell, ...]:
    target = region.rectangle
    kernel = kernel_cells(board, region.center)
    assigned_cells = set(kernel)

    current_top = min(cell.row for cell in kernel)
    current_bottom = max(cell.row for cell in kernel)
    current_left = min(cell.col for cell in kernel)
    current_right = max(cell.col for cell in kernel)

    # Grow from the kernel by symmetric outer strips until the full target
    # rectangle is reached. Each strip keeps symmetry and connectivity intact.
    while (
        current_top != target.top
        or current_bottom != target.bottom
        or current_left != target.left
        or current_right != target.right
    ):
        remaining_rows = current_top - target.top
        remaining_cols = current_left - target.left

        if remaining_rows >= remaining_cols and remaining_rows > 0:
            current_top -= 1
            current_bottom += 1
            for col in range(current_left, current_right + 1):
                assigned_cells.add(Cell(row=current_top, col=col))
                assigned_cells.add(Cell(row=current_bottom, col=col))
            continue

        if remaining_cols > 0:
            current_left -= 1
            current_right += 1
            for row in range(current_top, current_bottom + 1):
                assigned_cells.add(Cell(row=row, col=current_left))
                assigned_cells.add(Cell(row=row, col=current_right))
            continue

        raise ValueError("Target rectangle cannot be reached from the current kernel.")

    return tuple(sorted(assigned_cells))


def grow_candidate_regions(
    board: BoardSpec,
    regions: tuple[PlacedCenterRegion, ...],
):
    """Grow one constructive assignment from kernels to target regions."""

    return MappingProxyType(
        {
            region.id: _grow_one_rectangular_region(board, region)
            for region in regions
        }
    )


__all__ = ["grow_candidate_regions"]
