from __future__ import annotations

import unittest

from core import (
    BaseMilpModel,
    BoardSpec,
    Cell,
    CenterSpec,
    PuzzleData,
    solve_base_model,
    validate_assignment,
)


class Phase4BaseMilpTests(unittest.TestCase):
    def test_model_uses_canonical_variable_order_and_constraint_counts(self) -> None:
        board = BoardSpec(rows=1, cols=2)
        centers = [
            CenterSpec.from_coordinates("g0", 0, 0),
            CenterSpec.from_coordinates("g1", 0, 1),
        ]
        puzzle_data = PuzzleData.from_specs(board, centers)

        model = BaseMilpModel.from_puzzle_data(puzzle_data)

        self.assertEqual(model.num_variables, 4)
        self.assertEqual(
            model.variable_keys,
            (
                (Cell(0, 0), "g0"),
                (Cell(0, 0), "g1"),
                (Cell(0, 1), "g0"),
                (Cell(0, 1), "g1"),
            ),
        )
        self.assertEqual(model.variable_index(Cell(0, 1), "g1"), 3)
        self.assertEqual(model.partition_row_count, 2)
        self.assertEqual(model.inadmissibility_row_count, 2)
        self.assertEqual(model.symmetry_row_count, 0)
        self.assertEqual(model.kernel_row_count, 2)

    def test_model_builds_symmetry_rows_for_nontrivial_rotation_pairs(self) -> None:
        board = BoardSpec(rows=1, cols=2)
        center = CenterSpec.from_coordinates("g0", 0, 0.5)
        puzzle_data = PuzzleData.from_specs(board, [center])

        model = BaseMilpModel.from_puzzle_data(puzzle_data)

        self.assertEqual(model.num_variables, 2)
        self.assertEqual(model.partition_row_count, 2)
        self.assertEqual(model.inadmissibility_row_count, 0)
        self.assertEqual(model.symmetry_row_count, 1)
        self.assertEqual(model.kernel_row_count, 2)

    def test_solver_returns_structured_assignment_for_simple_feasible_puzzle(self) -> None:
        board = BoardSpec(rows=1, cols=2)
        centers = [
            CenterSpec.from_coordinates("g0", 0, 0),
            CenterSpec.from_coordinates("g1", 0, 1),
        ]
        puzzle_data = PuzzleData.from_specs(board, centers)

        result = solve_base_model(puzzle_data)

        self.assertTrue(result.success)
        self.assertIsNotNone(result.assignment)
        self.assertEqual(result.assignment.assigned_center_by_cell[Cell(0, 0)], "g0")
        self.assertEqual(result.assignment.assigned_center_by_cell[Cell(0, 1)], "g1")
        self.assertEqual(result.assignment.cells_by_center["g0"], (Cell(0, 0),))
        self.assertEqual(result.assignment.cells_by_center["g1"], (Cell(0, 1),))

        validation = validate_assignment(puzzle_data, result.assignment.cells_by_center)
        self.assertTrue(validation.partition_ok)
        self.assertTrue(validation.admissibility_ok)
        self.assertTrue(validation.symmetry_ok)
        self.assertTrue(validation.kernel_ok)
        self.assertTrue(validation.is_valid)

    def test_solver_handles_nontrivial_symmetry_pair(self) -> None:
        board = BoardSpec(rows=1, cols=2)
        center = CenterSpec.from_coordinates("g0", 0, 0.5)
        puzzle_data = PuzzleData.from_specs(board, [center])

        result = solve_base_model(puzzle_data)

        self.assertTrue(result.success)
        self.assertIsNotNone(result.assignment)
        self.assertEqual(
            result.assignment.cells_by_center["g0"],
            (Cell(0, 0), Cell(0, 1)),
        )

        validation = validate_assignment(puzzle_data, result.assignment.cells_by_center)
        self.assertTrue(validation.symmetry_ok)
        self.assertTrue(validation.kernel_ok)
        self.assertTrue(validation.is_valid)


if __name__ == "__main__":
    unittest.main()
