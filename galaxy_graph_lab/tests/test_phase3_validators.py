from __future__ import annotations

import unittest

from core import (
    AssignmentValidationResult,
    BoardSpec,
    Cell,
    CenterSpec,
    PuzzleData,
    admissibility_is_valid,
    connectivity_is_valid,
    kernel_is_valid,
    partition_is_valid,
    symmetry_is_valid,
    validate_assignment,
)


class Phase3ValidatorTests(unittest.TestCase):
    def test_partition_validator_requires_exact_cover_without_overlap(self) -> None:
        board = BoardSpec(rows=1, cols=2)
        centers = [
            CenterSpec.from_coordinates("g0", 0, 0),
            CenterSpec.from_coordinates("g1", 0, 1),
        ]
        puzzle_data = PuzzleData.from_specs(board, centers)

        valid_assignment = {
            "g0": (Cell(0, 0),),
            "g1": (Cell(0, 1),),
        }
        missing_cell_assignment = {
            "g0": (Cell(0, 0),),
        }
        overlapping_assignment = {
            "g0": (Cell(0, 0), Cell(0, 1)),
            "g1": (Cell(0, 1),),
        }

        self.assertTrue(partition_is_valid(puzzle_data, valid_assignment))
        self.assertFalse(partition_is_valid(puzzle_data, missing_cell_assignment))
        self.assertFalse(partition_is_valid(puzzle_data, overlapping_assignment))

    def test_admissibility_validator_rejects_cells_outside_center_domain(self) -> None:
        board = BoardSpec(rows=3, cols=3)
        center = CenterSpec.from_coordinates("g0", 0, 0)
        puzzle_data = PuzzleData.from_specs(board, [center])

        self.assertTrue(
            admissibility_is_valid(
                puzzle_data,
                {"g0": (Cell(0, 0),)},
            )
        )
        self.assertFalse(
            admissibility_is_valid(
                puzzle_data,
                {"g0": (Cell(0, 1),)},
            )
        )

    def test_symmetry_validator_requires_twin_pairs(self) -> None:
        board = BoardSpec(rows=3, cols=3)
        center = CenterSpec.from_coordinates("g0", 1, 1)
        puzzle_data = PuzzleData.from_specs(board, [center])

        self.assertTrue(
            symmetry_is_valid(
                puzzle_data,
                {"g0": (Cell(1, 1), Cell(0, 1), Cell(2, 1))},
            )
        )
        self.assertFalse(
            symmetry_is_valid(
                puzzle_data,
                {"g0": (Cell(1, 1), Cell(0, 1))},
            )
        )

    def test_kernel_validator_requires_all_kernel_cells(self) -> None:
        board = BoardSpec(rows=4, cols=5)
        center = CenterSpec.from_coordinates("g0", 1, 2.5)
        puzzle_data = PuzzleData.from_specs(board, [center])

        self.assertTrue(
            kernel_is_valid(
                puzzle_data,
                {"g0": (Cell(1, 2), Cell(1, 3))},
            )
        )
        self.assertFalse(
            kernel_is_valid(
                puzzle_data,
                {"g0": (Cell(1, 2),)},
            )
        )

    def test_connectivity_validator_rejects_disconnected_regions(self) -> None:
        board = BoardSpec(rows=3, cols=3)
        center = CenterSpec.from_coordinates("g0", 1, 1)
        puzzle_data = PuzzleData.from_specs(board, [center])

        self.assertTrue(
            connectivity_is_valid(
                puzzle_data,
                {"g0": (Cell(1, 1), Cell(1, 0), Cell(1, 2))},
            )
        )
        self.assertFalse(
            connectivity_is_valid(
                puzzle_data,
                {"g0": (Cell(0, 0), Cell(1, 1), Cell(2, 2))},
            )
        )

    def test_validate_assignment_collects_phase3_flags(self) -> None:
        board = BoardSpec(rows=2, cols=2)
        center = CenterSpec.from_coordinates("g0", 0.5, 0.5)
        puzzle_data = PuzzleData.from_specs(board, [center])

        valid_result = validate_assignment(
            puzzle_data,
            {"g0": board.cells()},
        )
        invalid_result = validate_assignment(
            puzzle_data,
            {"g0": (Cell(0, 0),)},
        )

        self.assertIsInstance(valid_result, AssignmentValidationResult)
        self.assertTrue(valid_result.partition_ok)
        self.assertTrue(valid_result.admissibility_ok)
        self.assertTrue(valid_result.symmetry_ok)
        self.assertTrue(valid_result.kernel_ok)
        self.assertTrue(valid_result.connectivity_ok)
        self.assertTrue(valid_result.is_valid)

        self.assertFalse(invalid_result.partition_ok)
        self.assertTrue(invalid_result.admissibility_ok)
        self.assertFalse(invalid_result.symmetry_ok)
        self.assertFalse(invalid_result.kernel_ok)
        self.assertTrue(invalid_result.connectivity_ok)
        self.assertFalse(invalid_result.is_valid)


if __name__ == "__main__":
    unittest.main()
