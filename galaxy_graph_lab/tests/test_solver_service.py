from __future__ import annotations

import unittest
from unittest.mock import patch

from galaxy_graph_lab.core import (
    BoardSpec,
    Cell,
    CenterSpec,
    EXACT_FLOW_SOLVER_BACKEND,
    FlowMilpSolveResult,
    PARALLEL_CALLBACK_SOLVER_BACKEND,
    PuzzleData,
    PuzzleSolveResult,
    SOLVER_STATUS_BACKEND_UNAVAILABLE,
    SOLVER_STATUS_ERROR,
    SOLVER_STATUS_INFEASIBLE,
    SOLVER_STATUS_SOLVED,
    SOLVER_STATUS_UNSUPPORTED_BACKEND,
    solve_puzzle,
    validate_assignment,
)


class SolverServiceTests(unittest.TestCase):
    def _guided_puzzle_data(self) -> PuzzleData:
        return PuzzleData.from_specs(
            BoardSpec(rows=3, cols=3),
            [
                CenterSpec.from_coordinates("A", 0, 1),
                CenterSpec.from_coordinates("B", 1.5, 1),
            ],
        )

    def test_solve_puzzle_wraps_exact_flow_as_public_entrypoint(self) -> None:
        board = BoardSpec(rows=1, cols=3)
        center = CenterSpec.from_coordinates("g0", 0, 1)
        puzzle_data = PuzzleData.from_specs(board, [center])

        result = solve_puzzle(puzzle_data)

        self.assertIsInstance(result, PuzzleSolveResult)
        self.assertTrue(result.success)
        self.assertEqual(result.backend_name, EXACT_FLOW_SOLVER_BACKEND)
        self.assertEqual(result.status_label, SOLVER_STATUS_SOLVED)
        self.assertEqual(result.message, "Solution found.")
        self.assertIsNotNone(result.assignment)
        self.assertEqual(
            result.assignment.cells_by_center["g0"],
            (Cell(0, 0), Cell(0, 1), Cell(0, 2)),
        )

        validation = validate_assignment(puzzle_data, result.assignment.cells_by_center)
        self.assertTrue(validation.is_valid)

    def test_solve_puzzle_keeps_all_current_selections_when_that_is_feasible(self) -> None:
        puzzle_data = self._guided_puzzle_data()

        result = solve_puzzle(
            puzzle_data,
            preferred_assignment_by_cell={
                Cell(0, 0): "A",
                Cell(1, 0): "B",
            },
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status_label, SOLVER_STATUS_SOLVED)
        self.assertEqual(result.solution_mode, "guided_exact")
        self.assertEqual(result.preferred_assignment_count, 2)
        self.assertEqual(result.matched_preference_count, 2)
        self.assertEqual(result.mismatch_count, 0)
        self.assertEqual(
            result.message,
            "Solution found and it keeps all current selections.",
        )
        self.assertEqual(result.assignment.assigned_center_by_cell[Cell(0, 0)], "A")
        self.assertEqual(result.assignment.assigned_center_by_cell[Cell(1, 0)], "B")

    def test_solve_puzzle_falls_back_to_minimum_mismatch_solution(self) -> None:
        puzzle_data = self._guided_puzzle_data()

        result = solve_puzzle(
            puzzle_data,
            preferred_assignment_by_cell={
                Cell(0, 0): "A",
                Cell(1, 0): "A",
            },
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status_label, SOLVER_STATUS_SOLVED)
        self.assertEqual(result.solution_mode, "guided_min_mismatch")
        self.assertEqual(result.preferred_assignment_count, 2)
        self.assertEqual(result.matched_preference_count, 1)
        self.assertEqual(result.mismatch_count, 1)
        self.assertEqual(
            result.message,
            "Current selections cannot all be satisfied. Loaded the closest solution with 1 mismatch(es).",
        )
        self.assertEqual(result.assignment.assigned_center_by_cell[Cell(0, 0)], "A")
        self.assertEqual(result.assignment.assigned_center_by_cell[Cell(1, 0)], "B")

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
        self.assertEqual(result.backend_name, EXACT_FLOW_SOLVER_BACKEND)
        self.assertEqual(result.status_code, 9)
        self.assertEqual(result.status_label, SOLVER_STATUS_ERROR)
        self.assertEqual(
            result.message,
            "The solver could not complete successfully: backend unavailable",
        )
        self.assertIsNone(result.assignment)

    def test_solve_puzzle_reports_infeasible_puzzle_with_ui_friendly_message(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=1),
            [CenterSpec.from_coordinates("g0", 0, 0)],
        )
        backend_result = FlowMilpSolveResult(
            success=False,
            status=2,
            message="The problem is infeasible.",
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
        ):
            result = solve_puzzle(puzzle_data)

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 2)
        self.assertEqual(result.status_label, SOLVER_STATUS_INFEASIBLE)
        self.assertEqual(result.message, "No feasible solution exists for this puzzle.")
        self.assertIsNone(result.assignment)

    def test_solve_puzzle_reports_unsupported_backend(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=1),
            [CenterSpec.from_coordinates("g0", 0, 0)],
        )

        result = solve_puzzle(puzzle_data, backend="mock_backend")

        self.assertFalse(result.success)
        self.assertEqual(result.backend_name, "mock_backend")
        self.assertEqual(result.status_code, -1)
        self.assertEqual(result.status_label, SOLVER_STATUS_UNSUPPORTED_BACKEND)
        self.assertEqual(
            result.message,
            "Solver backend 'mock_backend' is not supported.",
        )
        self.assertIsNone(result.assignment)

    def test_solve_puzzle_dispatches_parallel_callback_backend(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=1),
            [CenterSpec.from_coordinates("g0", 0, 0)],
        )

        with patch("galaxy_graph_lab.core.solver_service.solve_flow_model") as solve_flow_mock:
            result = solve_puzzle(puzzle_data, backend=PARALLEL_CALLBACK_SOLVER_BACKEND)

        solve_flow_mock.assert_not_called()
        self.assertFalse(result.success)
        self.assertEqual(result.backend_name, PARALLEL_CALLBACK_SOLVER_BACKEND)
        self.assertEqual(result.status_code, -2)
        self.assertEqual(result.status_label, SOLVER_STATUS_BACKEND_UNAVAILABLE)
        self.assertEqual(
            result.message,
            "Solver backend 'parallel_callback' is unavailable: callback-parallel backend is not implemented yet.",
        )
        self.assertIsNone(result.assignment)

    def test_solve_puzzle_reports_backend_unavailable(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=1),
            [CenterSpec.from_coordinates("g0", 0, 0)],
        )

        with patch(
            "galaxy_graph_lab.core.solver_service.solve_flow_model",
            side_effect=ModuleNotFoundError("No module named 'scipy'"),
        ):
            result = solve_puzzle(puzzle_data)

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, -2)
        self.assertEqual(result.status_label, SOLVER_STATUS_BACKEND_UNAVAILABLE)
        self.assertEqual(
            result.message,
            "Solver backend 'exact_flow' is unavailable: No module named 'scipy'.",
        )
        self.assertIsNone(result.assignment)

    def test_solve_puzzle_reports_internal_solver_error(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=1),
            [CenterSpec.from_coordinates("g0", 0, 0)],
        )

        with patch(
            "galaxy_graph_lab.core.solver_service.solve_flow_model",
            side_effect=RuntimeError("unexpected failure"),
        ):
            result = solve_puzzle(puzzle_data)

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, -3)
        self.assertEqual(result.status_label, SOLVER_STATUS_ERROR)
        self.assertEqual(
            result.message,
            "The solver raised an internal error: unexpected failure.",
        )
        self.assertIsNone(result.assignment)


if __name__ == "__main__":
    unittest.main()
