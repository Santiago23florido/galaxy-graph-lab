from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from galaxy_graph_lab.core import BoardSpec, Cell, CenterSpec, PuzzleData, validate_assignment
from galaxy_graph_lab.ui.app import run_phase_d_app
from galaxy_graph_lab.ui.game_state import EditablePuzzleState
from galaxy_graph_lab.ui.renderer import GeometryHit


class PhaseDPygameUiTests(unittest.TestCase):
    def test_candidate_assignment_keeps_all_centers(self) -> None:
        state = EditablePuzzleState.from_center_ids(("A", "B"))
        state.apply_left_click(GeometryHit(kind="center", center_id="A"))
        state.apply_left_click(GeometryHit(kind="cell", cell=Cell(2, 3)))

        self.assertEqual(
            dict(state.candidate_assignment()),
            {
                "A": (Cell(2, 3),),
                "B": (),
            },
        )

    def test_live_validation_changes_with_the_current_ui_assignment(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=1),
            (CenterSpec.from_coordinates("A", 0, 0),),
        )
        state = EditablePuzzleState.from_center_ids(("A",))

        empty_validation = validate_assignment(puzzle_data, state.candidate_assignment())
        self.assertFalse(empty_validation.is_valid)
        self.assertFalse(empty_validation.partition_ok)
        self.assertFalse(empty_validation.kernel_ok)

        state.apply_left_click(GeometryHit(kind="center", center_id="A"))
        state.apply_left_click(GeometryHit(kind="cell", cell=Cell(0, 0)))

        filled_validation = validate_assignment(puzzle_data, state.candidate_assignment())
        self.assertTrue(filled_validation.is_valid)

    def test_phase_d_app_runs_headless_for_one_frame(self) -> None:
        with patch.dict(
            os.environ,
            {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"},
            clear=False,
        ):
            run_phase_d_app(max_frames=1)


if __name__ == "__main__":
    unittest.main()
