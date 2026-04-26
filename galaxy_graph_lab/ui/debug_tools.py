from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ..core import Cell, PuzzleData


@dataclass(slots=True)
class DebugOverlayState:
    """Mutable debug toggles for optional developer overlays."""

    show_admissible_domain: bool = False
    show_kernel_cells: bool = False
    show_components: bool = False
    show_solver_comparison: bool = False


def component_index_by_cell(
    puzzle_data: PuzzleData,
    cells: Iterable[Cell],
) -> Mapping[Cell, int]:
    selected_cells = tuple(cells)
    if not selected_cells:
        return MappingProxyType({})

    components = puzzle_data.graph.connected_components(selected_cells)
    return MappingProxyType(
        {
            cell: component_index
            for component_index, component in enumerate(components)
            for cell in component
        }
    )


def comparison_by_cell(
    current_assignment_by_cell: Mapping[Cell, str],
    exact_assignment_by_cell: Mapping[Cell, str],
    *,
    cells_to_compare: Iterable[Cell] | None = None,
) -> Mapping[Cell, bool]:
    if cells_to_compare is None:
        cells = tuple(current_assignment_by_cell)
    else:
        cells = tuple(cells_to_compare)
    return MappingProxyType(
        {
            cell: current_assignment_by_cell.get(cell) == exact_assignment_by_cell.get(cell)
            for cell in cells
        }
    )


def comparison_counts(comparison_lookup: Mapping[Cell, bool]) -> tuple[int, int]:
    match_count = sum(1 for is_match in comparison_lookup.values() if is_match)
    mismatch_count = len(comparison_lookup) - match_count
    return match_count, mismatch_count


__all__ = [
    "DebugOverlayState",
    "comparison_by_cell",
    "comparison_counts",
    "component_index_by_cell",
]
