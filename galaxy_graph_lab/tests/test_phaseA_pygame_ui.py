from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from galaxy_graph_lab.core import Cell
from galaxy_graph_lab.ui.app import run_phase_b_app
from galaxy_graph_lab.ui.puzzle_loader import load_phase_a_puzzle
from galaxy_graph_lab.ui.renderer import (
    build_board_layout,
    center_at_pixel,
    center_position,
    cell_at_pixel,
    cell_rect,
    hit_test_board_geometry,
)


class PhaseAPygameUiTests(unittest.TestCase):
    def test_fixed_puzzle_builds_expected_geometry(self) -> None:
        puzzle = load_phase_a_puzzle()

        self.assertEqual(puzzle.name, "Phase A Demo")
        self.assertEqual(puzzle.puzzle_data.board.rows, 7)
        self.assertEqual(puzzle.puzzle_data.board.cols, 7)
        self.assertEqual(len(puzzle.puzzle_data.centers), 5)

    def test_layout_scales_from_board_dimensions(self) -> None:
        puzzle = load_phase_a_puzzle()
        layout = build_board_layout(puzzle.puzzle_data)

        self.assertEqual(layout.board_width, 7 * layout.cell_size)
        self.assertEqual(layout.board_height, 7 * layout.cell_size)
        self.assertGreater(layout.window_width, layout.board_width)
        self.assertGreater(layout.window_height, layout.board_height)

    def test_cell_hit_testing_maps_pixel_back_to_cell(self) -> None:
        puzzle = load_phase_a_puzzle()
        layout = build_board_layout(puzzle.puzzle_data)
        target_cell = Cell(2, 3)
        rect = cell_rect(layout, target_cell)
        pixel = rect.center

        self.assertEqual(cell_at_pixel(puzzle.puzzle_data, layout, pixel), target_cell)

    def test_center_hit_testing_maps_pixel_back_to_center(self) -> None:
        puzzle = load_phase_a_puzzle()
        layout = build_board_layout(puzzle.puzzle_data)
        target_center = puzzle.puzzle_data.centers[2]
        pixel = center_position(layout, target_center)

        hit_center = center_at_pixel(puzzle.puzzle_data, layout, pixel)

        self.assertIsNotNone(hit_center)
        self.assertEqual(hit_center.id, target_center.id)

    def test_center_hit_testing_has_priority_over_cell_hit(self) -> None:
        puzzle = load_phase_a_puzzle()
        layout = build_board_layout(puzzle.puzzle_data)
        target_center = puzzle.puzzle_data.centers[0]
        pixel = center_position(layout, target_center)

        hit = hit_test_board_geometry(puzzle.puzzle_data, layout, pixel)

        self.assertIsNotNone(hit)
        self.assertEqual(hit.kind, "center")
        self.assertEqual(hit.center_id, target_center.id)

    def test_hit_testing_returns_none_outside_board_and_centers(self) -> None:
        puzzle = load_phase_a_puzzle()
        layout = build_board_layout(puzzle.puzzle_data)

        self.assertIsNone(hit_test_board_geometry(puzzle.puzzle_data, layout, (5, 5)))

    def test_phase_a_app_runs_headless_for_one_frame(self) -> None:
        with patch.dict(
            os.environ,
            {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"},
            clear=False,
        ):
            run_phase_b_app(max_frames=1)


if __name__ == "__main__":
    unittest.main()
