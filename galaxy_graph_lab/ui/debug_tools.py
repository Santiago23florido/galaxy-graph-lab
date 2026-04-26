from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ..core import Cell, FlowMilpSolveResult, PuzzleData, solve_flow_model


@dataclass(slots=True)
class DebugOverlayState:
    """Mutable debug toggles and cached exact-flow solver result."""

    show_admissible_domain: bool = False
    show_kernel_cells: bool = False
    show_components: bool = False
    show_solver_comparison: bool = False
    exact_flow_result: FlowMilpSolveResult | None = None

    def ensure_exact_flow_result(self, puzzle_data: PuzzleData) -> FlowMilpSolveResult:
        if self.exact_flow_result is None:
            self.exact_flow_result = solve_flow_model(puzzle_data)
        return self.exact_flow_result

    def exact_assignment_by_cell(self) -> Mapping[Cell, str] | None:
        if self.exact_flow_result is None or self.exact_flow_result.assignment is None:
            return None
        return self.exact_flow_result.assignment.assigned_center_by_cell


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
) -> Mapping[Cell, bool]:
    all_cells = set(current_assignment_by_cell).union(exact_assignment_by_cell)
    return MappingProxyType(
        {
            cell: current_assignment_by_cell.get(cell) == exact_assignment_by_cell.get(cell)
            for cell in all_cells
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
