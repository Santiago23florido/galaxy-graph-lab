from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from ..board import BoardSpec, Cell
from .center_placement import PlacedCenterRegion


@dataclass(frozen=True, slots=True)
class PartitionClosureResult:
    """Structured result of closing one constructive partition candidate."""

    success: bool
    cells_by_center: MappingProxyType | None
    message: str


def close_candidate_partition(
    board: BoardSpec,
    regions: tuple[PlacedCenterRegion, ...],
    cells_by_center,
) -> PartitionClosureResult:
    """Verify that the grown regions cover the full board without overlaps."""

    assigned_center_by_cell: dict[Cell, str] = {}

    for region in regions:
        region_cells = tuple(cells_by_center[region.id])
        if set(region_cells) != set(region.cells()):
            return PartitionClosureResult(
                success=False,
                cells_by_center=None,
                message=f"Region {region.id} does not match its target rectangle.",
            )

        for cell in region_cells:
            if cell in assigned_center_by_cell:
                return PartitionClosureResult(
                    success=False,
                    cells_by_center=None,
                    message=f"Cell {cell} was assigned by multiple regions.",
                )
            assigned_center_by_cell[cell] = region.id

    if set(assigned_center_by_cell) != set(board.cells()):
        return PartitionClosureResult(
            success=False,
            cells_by_center=None,
            message="Constructive partition does not cover the full board.",
        )

    return PartitionClosureResult(
        success=True,
        cells_by_center=MappingProxyType(
            {
                center_id: tuple(sorted(center_cells))
                for center_id, center_cells in cells_by_center.items()
            }
        ),
        message="Constructive partition closed successfully.",
    )


__all__ = ["PartitionClosureResult", "close_candidate_partition"]
