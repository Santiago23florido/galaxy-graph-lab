"""Tests for the Phase 1 geometry layer."""

from __future__ import annotations

import unittest

from galaxy_graph_lab.core import (
    BoardSpec,
    Cell,
    CenterSpec,
    PuzzleData,
    admissible_cells,
    kernel_cells,
    tau,
    twin_cell,
)


class Phase1GeometryTests(unittest.TestCase):
    def test_center_inside_cell(self) -> None:
        board = BoardSpec(rows=4, cols=4)
        center = CenterSpec.from_coordinates("g0", 1, 2)

        self.assertEqual(kernel_cells(board, center), (Cell(1, 2),))
        self.assertEqual(tau(center, Cell(0, 2)), (2, 2))
        self.assertEqual(twin_cell(board, center, Cell(0, 2)), Cell(2, 2))

    def test_center_on_edge_has_two_kernel_cells(self) -> None:
        board = BoardSpec(rows=4, cols=5)
        center = CenterSpec.from_coordinates("g1", 1, 2.5)

        self.assertEqual(kernel_cells(board, center), (Cell(1, 2), Cell(1, 3)))
        self.assertEqual(twin_cell(board, center, Cell(0, 1)), Cell(2, 4))
        self.assertIsNone(twin_cell(board, center, Cell(0, 0)))

    def test_center_on_vertex_has_four_kernel_cells(self) -> None:
        board = BoardSpec(rows=5, cols=5)
        center = CenterSpec.from_coordinates("g2", 2.5, 2.5)

        self.assertEqual(
            kernel_cells(board, center),
            (Cell(2, 2), Cell(2, 3), Cell(3, 2), Cell(3, 3)),
        )
        self.assertEqual(twin_cell(board, center, Cell(1, 1)), Cell(4, 4))

    def test_admissible_domain_filters_invalid_twins(self) -> None:
        board = BoardSpec(rows=3, cols=3)
        center = CenterSpec.from_coordinates("g3", 0, 0)

        self.assertEqual(admissible_cells(board, center), (Cell(0, 0),))
        puzzle_data = PuzzleData.from_specs(board, [center])

        self.assertEqual(puzzle_data.kernel_by_center["g3"], (Cell(0, 0),))

    def test_invalid_fractional_center_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CenterSpec.from_coordinates("bad", 1.25, 2)

    def test_duplicate_center_ids_are_rejected(self) -> None:
        board = BoardSpec(rows=4, cols=4)
        centers = [
            CenterSpec.from_coordinates("dup", 1, 1),
            CenterSpec.from_coordinates("dup", 2, 2),
        ]

        with self.assertRaises(ValueError):
            PuzzleData.from_specs(board, centers)


if __name__ == "__main__":
    unittest.main()
