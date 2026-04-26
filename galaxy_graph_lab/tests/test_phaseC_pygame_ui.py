from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from galaxy_graph_lab.core import Cell
from galaxy_graph_lab.ui.app import run_phase_c_app
from galaxy_graph_lab.ui.game_state import EditablePuzzleState
from galaxy_graph_lab.ui.renderer import GeometryHit


class PhaseCPygameUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = EditablePuzzleState.from_center_ids(("A", "B", "C"))

    def test_clicking_center_selects_it(self) -> None:
        self.state.apply_left_click(GeometryHit(kind="center", center_id="B"))

        self.assertEqual(self.state.selected_center_id, "B")
        self.assertEqual(self.state.last_hit, GeometryHit(kind="center", center_id="B"))

    def test_clicking_cell_assigns_it_to_selected_center(self) -> None:
        self.state.apply_left_click(GeometryHit(kind="center", center_id="A"))
        self.state.apply_left_click(GeometryHit(kind="cell", cell=Cell(2, 3)))

        self.assertEqual(self.state.assigned_center_for_cell(Cell(2, 3)), "A")

    def test_clicking_same_cell_again_clears_it(self) -> None:
        hit = GeometryHit(kind="cell", cell=Cell(1, 1))
        self.state.apply_left_click(GeometryHit(kind="center", center_id="A"))
        self.state.apply_left_click(hit)
        self.state.apply_left_click(hit)

        self.assertIsNone(self.state.assigned_center_for_cell(Cell(1, 1)))

    def test_clicking_cell_with_different_selected_center_reassigns_it(self) -> None:
        hit = GeometryHit(kind="cell", cell=Cell(4, 5))
        self.state.apply_left_click(GeometryHit(kind="center", center_id="A"))
        self.state.apply_left_click(hit)
        self.state.apply_left_click(GeometryHit(kind="center", center_id="C"))
        self.state.apply_left_click(hit)

        self.assertEqual(self.state.assigned_center_for_cell(Cell(4, 5)), "C")

    def test_clicking_cell_without_selected_center_does_nothing(self) -> None:
        self.state.apply_left_click(GeometryHit(kind="cell", cell=Cell(0, 0)))

        self.assertIsNone(self.state.assigned_center_for_cell(Cell(0, 0)))

    def test_reset_assignments_clears_state(self) -> None:
        self.state.apply_left_click(GeometryHit(kind="center", center_id="A"))
        self.state.apply_left_click(GeometryHit(kind="cell", cell=Cell(0, 1)))
        self.state.reset_assignments()

        self.assertEqual(dict(self.state.assigned_center_by_cell), {})
        self.assertIsNone(self.state.last_hit)

    def test_phase_c_app_runs_headless_for_one_frame(self) -> None:
        with patch.dict(
            os.environ,
            {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"},
            clear=False,
        ):
            run_phase_c_app(max_frames=1)


if __name__ == "__main__":
    unittest.main()
