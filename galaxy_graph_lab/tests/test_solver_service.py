from __future__ import annotations

import unittest
from unittest.mock import patch

from galaxy_graph_lab.core import (
    BoardSpec,
    Cell,
    CenterSpec,
    FlowMilpSolveResult,
    PuzzleData,
    PuzzleSolveResult,
    solve_puzzle,
    validate_assignment,
)


class SolverServiceTests(unittest.TestCase):
    def test_solve_puzzle_wraps_exact_flow_as_public_entrypoint(self) -> None:
        board = BoardSpec(rows=1, cols=3)
        center = CenterSpec.from_coordinates("g0", 0, 1)
        puzzle_data = PuzzleData.from_specs(board, [center])

        result = solve_puzzle(puzzle_data)

        self.assertIsInstance(result, PuzzleSolveResult)
        self.assertTrue(result.success)
        self.assertEqual(result.backend_name, "exact_flow")
        self.assertIsNotNone(result.assignment)
        self.assertEqual(
            result.assignment.cells_by_center["g0"],
            (Cell(0, 0), Cell(0, 1), Cell(0, 2)),
        )

        validation = validate_assignment(puzzle_data, result.assignment.cells_by_center)
        self.assertTrue(validation.is_valid)

    def test_solve_puzzle_normalizes_backend_result_shape(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=1),
            [CenterSpec.from_coordinates("g0", 0, 0)],
        )
        backend_result = FlowMilpSolveResult(
            success=False,
            status=9,
            message="backend unavailable",
            objective_value=None,
            mip_gap=None,
            mip_node_count=None,
            assignment=None,
            assignment_variable_values=None,
            directed_flow_values=None,
            source_flow_values=None,
        )

        with patch(
            "galaxy_graph_lab.core.solver_service.solve_flow_model",
            return_value=backend_result,
        ) as solve_flow_mock:
            result = solve_puzzle(puzzle_data)

        solve_flow_mock.assert_called_once_with(puzzle_data, options=None)
        self.assertIsInstance(result, PuzzleSolveResult)
        self.assertFalse(result.success)
        self.assertEqual(result.backend_name, "exact_flow")
        self.assertEqual(result.status_code, 9)
        self.assertEqual(result.message, "backend unavailable")
        self.assertIsNone(result.assignment)


if __name__ == "__main__":
    unittest.main()
