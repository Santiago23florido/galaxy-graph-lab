from __future__ import annotations

import unittest

from core import (
    BoardSpec,
    Cell,
    CenterSpec,
    FlowMilpModel,
    FlowMilpSolveResult,
    PuzzleData,
    solve_flow_model,
    validate_assignment,
)


class Phase5FlowMilpTests(unittest.TestCase):
    def test_flow_model_adds_directed_and_source_flow_layers(self) -> None:
        board = BoardSpec(rows=1, cols=3)
        center = CenterSpec.from_coordinates("g0", 0, 1)
        puzzle_data = PuzzleData.from_specs(board, [center])

        model = FlowMilpModel.from_puzzle_data(puzzle_data)

        self.assertEqual(model.num_assignment_variables, 3)
        self.assertEqual(model.num_directed_flow_variables, 4)
        self.assertEqual(model.num_source_flow_variables, 1)
        self.assertEqual(model.num_variables, 8)
        self.assertEqual(model.edge_tail_capacity_row_count, 4)
        self.assertEqual(model.edge_head_capacity_row_count, 4)
        self.assertEqual(model.source_capacity_row_count, 1)
        self.assertEqual(model.flow_balance_row_count, 3)
        self.assertEqual(model.source_supply_row_count, 1)
        self.assertEqual(
            model.directed_flow_variable_index("g0", Cell(0, 1), Cell(0, 2)),
            5,
        )
        self.assertEqual(model.source_flow_variable_index("g0", Cell(0, 1)), 7)

    def test_flow_solver_routes_units_from_kernel_to_non_kernel_cells(self) -> None:
        board = BoardSpec(rows=1, cols=3)
        center = CenterSpec.from_coordinates("g0", 0, 1)
        puzzle_data = PuzzleData.from_specs(board, [center])

        result = solve_flow_model(puzzle_data)

        self.assertIsInstance(result, FlowMilpSolveResult)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.assignment)
        self.assertIsNotNone(result.source_flow_values)
        self.assertIsNotNone(result.directed_flow_values)
        self.assertEqual(
            result.assignment.cells_by_center["g0"],
            (Cell(0, 0), Cell(0, 1), Cell(0, 2)),
        )
        self.assertAlmostEqual(
            result.source_flow_values[("g0", Cell(0, 1))],
            3.0,
        )
        self.assertTrue(
            any(value > 0.5 for value in result.directed_flow_values.values())
        )

        validation = validate_assignment(puzzle_data, result.assignment.cells_by_center)
        self.assertTrue(validation.partition_ok)
        self.assertTrue(validation.admissibility_ok)
        self.assertTrue(validation.symmetry_ok)
        self.assertTrue(validation.kernel_ok)
        self.assertTrue(validation.connectivity_ok)
        self.assertTrue(validation.is_valid)


if __name__ == "__main__":
    unittest.main()
