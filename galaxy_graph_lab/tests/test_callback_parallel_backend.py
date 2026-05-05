from __future__ import annotations

import unittest
from unittest.mock import patch

from galaxy_graph_lab.core import (
    BaseMilpSolveResult,
    BoardSpec,
    CallbackParallelMilpModel,
    Cell,
    CenterSpec,
    GalaxyAssignment,
    PuzzleData,
    solve_callback_parallel_model,
)


class CallbackParallelBackendTests(unittest.TestCase):
    def _puzzle_data(self) -> PuzzleData:
        return PuzzleData.from_specs(
            BoardSpec(rows=3, cols=3),
            [
                CenterSpec.from_coordinates("A", 0, 1),
                CenterSpec.from_coordinates("B", 1.5, 1),
            ],
        )

    def _assignment(
        self,
        assigned_center_by_cell: dict[Cell, str],
    ) -> GalaxyAssignment:
        cells_by_center_lists: dict[str, list[Cell]] = {"A": [], "B": []}
        for cell, center_id in assigned_center_by_cell.items():
            cells_by_center_lists[center_id].append(cell)
        return GalaxyAssignment(
            assigned_center_by_cell=assigned_center_by_cell,
            cells_by_center={
                center_id: tuple(cells)
                for center_id, cells in cells_by_center_lists.items()
            },
        )

    def _variable_values(
        self,
        model: CallbackParallelMilpModel,
        assignment: GalaxyAssignment,
    ) -> tuple[float, ...]:
        return tuple(
            1.0
            if assignment.assigned_center_by_cell[cell] == center_id
            else 0.0
            for cell, center_id in model.base_model.variable_keys
        )

    def test_internal_fallback_retries_after_disconnected_base_solution(self) -> None:
        puzzle_data = self._puzzle_data()
        model = CallbackParallelMilpModel.from_puzzle_data(puzzle_data)

        disconnected_assignment = self._assignment(
            {
                Cell(0, 0): "A",
                Cell(0, 1): "B",
                Cell(0, 2): "A",
                Cell(1, 0): "B",
                Cell(1, 1): "B",
                Cell(1, 2): "B",
                Cell(2, 0): "B",
                Cell(2, 1): "B",
                Cell(2, 2): "B",
            }
        )
        connected_assignment = self._assignment(
            {
                Cell(0, 0): "A",
                Cell(0, 1): "A",
                Cell(0, 2): "A",
                Cell(1, 0): "B",
                Cell(1, 1): "B",
                Cell(1, 2): "B",
                Cell(2, 0): "B",
                Cell(2, 1): "B",
                Cell(2, 2): "B",
            }
        )

        first_result = BaseMilpSolveResult(
            success=True,
            status=0,
            message="Optimization terminated successfully.",
            objective_value=0.0,
            mip_gap=0.0,
            mip_node_count=5,
            assignment=disconnected_assignment,
            variable_values=self._variable_values(model, disconnected_assignment),
        )
        second_result = BaseMilpSolveResult(
            success=True,
            status=0,
            message="Optimization terminated successfully.",
            objective_value=0.0,
            mip_gap=0.0,
            mip_node_count=7,
            assignment=connected_assignment,
            variable_values=self._variable_values(model, connected_assignment),
        )

        with patch(
            "galaxy_graph_lab.core.milp.base_model.BaseMilpModel.solve",
            side_effect=[first_result, second_result],
        ) as solve_mock:
            result = solve_callback_parallel_model(model)

        self.assertTrue(result.success)
        self.assertEqual(result.assignment, connected_assignment)
        self.assertEqual(result.mip_node_count, 12)
        self.assertIn("rejecting 1 disconnected incumbent", result.message)
        self.assertEqual(solve_mock.call_count, 2)
        first_call = solve_mock.call_args_list[0]
        second_call = solve_mock.call_args_list[1]
        self.assertEqual(first_call.kwargs["extra_constraints"], ())
        self.assertEqual(len(second_call.kwargs["extra_constraints"]), 1)

    def test_internal_fallback_reports_infeasible_after_excluding_disconnected_incumbent(
        self,
    ) -> None:
        puzzle_data = self._puzzle_data()
        model = CallbackParallelMilpModel.from_puzzle_data(puzzle_data)

        disconnected_assignment = self._assignment(
            {
                Cell(0, 0): "A",
                Cell(0, 1): "B",
                Cell(0, 2): "A",
                Cell(1, 0): "B",
                Cell(1, 1): "B",
                Cell(1, 2): "B",
                Cell(2, 0): "B",
                Cell(2, 1): "B",
                Cell(2, 2): "B",
            }
        )

        first_result = BaseMilpSolveResult(
            success=True,
            status=0,
            message="Optimization terminated successfully.",
            objective_value=0.0,
            mip_gap=0.0,
            mip_node_count=5,
            assignment=disconnected_assignment,
            variable_values=self._variable_values(model, disconnected_assignment),
        )
        second_result = BaseMilpSolveResult(
            success=False,
            status=2,
            message="The problem is infeasible.",
            objective_value=None,
            mip_gap=None,
            mip_node_count=3,
            assignment=None,
            variable_values=None,
        )

        with patch(
            "galaxy_graph_lab.core.milp.base_model.BaseMilpModel.solve",
            side_effect=[first_result, second_result],
        ) as solve_mock:
            result = solve_callback_parallel_model(model)

        self.assertFalse(result.success)
        self.assertEqual(result.status, 2)
        self.assertIsNone(result.assignment)
        self.assertEqual(result.mip_node_count, 8)
        self.assertIn("infeasible after excluding 1 disconnected incumbent", result.message)
        self.assertEqual(solve_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
