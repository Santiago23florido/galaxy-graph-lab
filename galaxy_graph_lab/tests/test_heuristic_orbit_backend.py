from __future__ import annotations

import unittest

from galaxy_graph_lab.core import (
    BoardSpec,
    Cell,
    CenterSpec,
    PuzzleData,
    solve_heuristic_orbit_model,
    validate_assignment,
)


class HeuristicOrbitBackendTests(unittest.TestCase):
    def _guided_puzzle_data(self) -> PuzzleData:
        return PuzzleData.from_specs(
            BoardSpec(rows=3, cols=3),
            [
                CenterSpec.from_coordinates("A", 0, 1),
                CenterSpec.from_coordinates("B", 1.5, 1),
            ],
        )

    def test_heuristic_orbit_solves_tiny_canonical_puzzle(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=3),
            [CenterSpec.from_coordinates("g0", 0, 1)],
        )

        result = solve_heuristic_orbit_model(
            puzzle_data,
            options={"time_limit": 1.0},
        )

        self.assertTrue(result.success)
        self.assertIsNotNone(result.assignment)
        validation = validate_assignment(
            puzzle_data,
            result.assignment.cells_by_center,
        )
        self.assertTrue(validation.is_valid)

    def test_heuristic_orbit_respects_feasible_preferred_assignment(self) -> None:
        puzzle_data = self._guided_puzzle_data()

        result = solve_heuristic_orbit_model(
            puzzle_data,
            options={"time_limit": 5.0, "random_seed": 0},
            preferred_assignment_by_cell={Cell(0, 0): "A"},
            require_preferred_assignment=True,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.assignment.assigned_center_by_cell[Cell(0, 0)], "A")
        validation = validate_assignment(
            puzzle_data,
            result.assignment.cells_by_center,
        )
        self.assertTrue(validation.is_valid)

    def test_heuristic_orbit_supports_avoidance_mismatch_guidance(self) -> None:
        puzzle_data = self._guided_puzzle_data()

        result = solve_heuristic_orbit_model(
            puzzle_data,
            options={"time_limit": 5.0, "random_seed": 1},
            avoid_assignment_by_cell={Cell(0, 0): "B"},
            minimum_mismatches_against_avoid=1,
        )

        self.assertTrue(result.success)
        self.assertNotEqual(result.assignment.assigned_center_by_cell[Cell(0, 0)], "B")
        validation = validate_assignment(
            puzzle_data,
            result.assignment.cells_by_center,
        )
        self.assertTrue(validation.is_valid)

    def test_heuristic_orbit_returns_timeout_failure(self) -> None:
        puzzle_data = self._guided_puzzle_data()

        result = solve_heuristic_orbit_model(
            puzzle_data,
            options={"time_limit": 1e-12},
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.assignment)
        self.assertIn("time limit", result.message.lower())


if __name__ == "__main__":
    unittest.main()
