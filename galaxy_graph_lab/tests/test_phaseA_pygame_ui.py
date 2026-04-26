from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ui.app import run_phase_a_app
from ui.puzzle_loader import load_phase_a_puzzle
from ui.renderer import build_board_layout


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

    def test_phase_a_app_runs_headless_for_one_frame(self) -> None:
        with patch.dict(
            os.environ,
            {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"},
            clear=False,
        ):
            run_phase_a_app(max_frames=1)


if __name__ == "__main__":
    unittest.main()
