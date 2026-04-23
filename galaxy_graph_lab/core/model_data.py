"""Immutable precomputed data shared by later solver layers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from .board import BoardSpec, Cell
from .centers import CenterSpec
from .geometry import admissible_cells, kernel_cells, twin_map


def _freeze_mapping(
    data: dict[str, tuple[Cell, ...]],
) -> Mapping[str, tuple[Cell, ...]]:
    return MappingProxyType(dict(data))


def _freeze_nested_mapping(
    data: dict[str, dict[Cell, Cell]],
) -> Mapping[str, Mapping[Cell, Cell]]:
    return MappingProxyType(
        {
            center_id: MappingProxyType(dict(cell_map))
            for center_id, cell_map in data.items()
        }
    )


@dataclass(frozen=True, slots=True)
class PuzzleData:
    """Solver-agnostic geometry precomputations for one puzzle."""

    board: BoardSpec
    cells: tuple[Cell, ...]
    centers: tuple[CenterSpec, ...]
    center_by_id: Mapping[str, CenterSpec]
    admissible_cells_by_center: Mapping[str, tuple[Cell, ...]]
    kernel_by_center: Mapping[str, tuple[Cell, ...]]
    twin_by_center_and_cell: Mapping[str, Mapping[Cell, Cell]]

    @classmethod
    def from_specs(
        cls,
        board: BoardSpec,
        centers: Sequence[CenterSpec],
    ) -> "PuzzleData":
        """Build the shared geometry data for Phase 1."""

        center_items = tuple(centers)
        if not center_items:
            raise ValueError("At least one center is required.")

        center_by_id: dict[str, CenterSpec] = {}
        admissible_by_center: dict[str, tuple[Cell, ...]] = {}
        kernel_by_center_lookup: dict[str, tuple[Cell, ...]] = {}
        twin_by_center_lookup: dict[str, dict[Cell, Cell]] = {}

        for center in center_items:
            if center.id in center_by_id:
                raise ValueError(f"Duplicate center id: {center.id}")

            admissible = admissible_cells(board=board, center=center)
            kernel = kernel_cells(board=board, center=center)
            twins = twin_map(board=board, center=center)

            if not kernel:
                raise ValueError(f"Center {center.id} does not touch the board.")

            if any(cell not in twins for cell in kernel):
                raise ValueError(
                    f"Center {center.id} has kernel cells outside its admissible domain."
                )

            center_by_id[center.id] = center
            admissible_by_center[center.id] = admissible
            kernel_by_center_lookup[center.id] = kernel
            twin_by_center_lookup[center.id] = twins

        return cls(
            board=board,
            cells=board.cells(),
            centers=center_items,
            center_by_id=MappingProxyType(dict(center_by_id)),
            admissible_cells_by_center=_freeze_mapping(admissible_by_center),
            kernel_by_center=_freeze_mapping(kernel_by_center_lookup),
            twin_by_center_and_cell=_freeze_nested_mapping(twin_by_center_lookup),
        )


__all__ = ["PuzzleData"]
