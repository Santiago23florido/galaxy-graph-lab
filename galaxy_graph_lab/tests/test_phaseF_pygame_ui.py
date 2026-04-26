from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from galaxy_graph_lab.core import BoardSpec, Cell, CenterSpec, PuzzleData
from galaxy_graph_lab.ui.app import run_phase_f_app
from galaxy_graph_lab.ui.debug_tools import (
    DebugOverlayState,
    comparison_by_cell,
    comparison_counts,
    component_index_by_cell,
)
from galaxy_graph_lab.ui.game_state import EditablePuzzleState


class PhaseFPygameUiTests(unittest.TestCase):
    def test_replace_assignments_loads_solver_like_mapping(self) -> None:
        state = EditablePuzzleState.from_center_ids(("A", "B"))
        state.replace_assignments({Cell(0, 0): "A", Cell(0, 1): "B"})

        self.assertEqual(
            dict(state.assigned_center_by_cell),
            {Cell(0, 0): "A", Cell(0, 1): "B"},
        )

    def test_component_index_by_cell_marks_disconnected_groups(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=2, cols=2),
            (CenterSpec.from_coordinates("A", 0.5, 0.5),),
        )

        component_lookup = component_index_by_cell(
            puzzle_data,
            (Cell(0, 0), Cell(1, 1)),
        )

        self.assertEqual(len(set(component_lookup.values())), 2)

    def test_comparison_by_cell_reports_match_and_mismatch_counts(self) -> None:
        comparison_lookup = comparison_by_cell(
            {Cell(0, 0): "A", Cell(0, 1): "B"},
            {Cell(0, 0): "A", Cell(0, 1): "A"},
        )

        self.assertEqual(comparison_lookup[Cell(0, 0)], True)
        self.assertEqual(comparison_lookup[Cell(0, 1)], False)
        self.assertEqual(comparison_counts(comparison_lookup), (1, 1))

    def test_debug_overlay_state_caches_exact_flow_result(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=1),
            (CenterSpec.from_coordinates("A", 0, 0),),
        )
        debug_state = DebugOverlayState()

        first_result = debug_state.ensure_exact_flow_result(puzzle_data)
        second_result = debug_state.ensure_exact_flow_result(puzzle_data)

        self.assertIs(first_result, second_result)
        self.assertTrue(first_result.success)
        self.assertEqual(dict(debug_state.exact_assignment_by_cell()), {Cell(0, 0): "A"})

    def test_phase_f_app_runs_headless_for_one_frame(self) -> None:
        with patch.dict(
            os.environ,
            {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"},
            clear=False,
        ):
            run_phase_f_app(max_frames=1)


if __name__ == "__main__":
    unittest.main()
