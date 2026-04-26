from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import pygame

from galaxy_graph_lab.core import BoardSpec, Cell, CenterSpec, GalaxyAssignment, PuzzleData
from galaxy_graph_lab.ui.app import run_phase_f_app
from galaxy_graph_lab.ui.debug_tools import (
    comparison_by_cell,
    comparison_counts,
    component_index_by_cell,
)
from galaxy_graph_lab.ui.game_state import EditablePuzzleState
from galaxy_graph_lab.ui.puzzle_loader import load_phase_a_puzzle
from galaxy_graph_lab.ui.renderer import build_board_layout, show_solution_button_rect
from galaxy_graph_lab.ui.solver_session import SolverSessionState


class PhaseFPygameUiTests(unittest.TestCase):
    def test_load_solver_assignment_replaces_the_full_tentative_board(self) -> None:
        state = EditablePuzzleState.from_center_ids(("A", "B"))
        state.replace_assignments({Cell(0, 0): "A", Cell(0, 1): "B"})
        state.last_hit = object()  # type: ignore[assignment]
        solver_assignment = GalaxyAssignment(
            assigned_center_by_cell={Cell(1, 0): "B"},
            cells_by_center={"A": (), "B": (Cell(1, 0),)},
        )

        state.load_solver_assignment(solver_assignment)

        self.assertEqual(
            dict(state.assigned_center_by_cell),
            {Cell(1, 0): "B"},
        )
        self.assertEqual(
            dict(state.candidate_assignment()),
            {"A": (), "B": (Cell(1, 0),)},
        )
        self.assertIsNone(state.last_hit)

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

    def test_solver_session_tracks_requested_cached_and_visible_flags(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=1),
            (CenterSpec.from_coordinates("A", 0, 0),),
        )
        solver_session = SolverSessionState()

        result = solver_session.request_solution(puzzle_data)

        self.assertTrue(result.success)
        self.assertTrue(solver_session.solver_result_requested)
        self.assertTrue(solver_session.solver_result_cached)
        self.assertEqual(solver_session.solver_status_label, "solved")
        self.assertEqual(solver_session.solver_message, "Solution found.")
        self.assertFalse(solver_session.solution_visible)
        self.assertFalse(solver_session.solution_loaded_into_board)
        self.assertEqual(dict(solver_session.solver_assignment_by_cell()), {Cell(0, 0): "A"})

        solver_session.mark_solution_loaded()
        self.assertTrue(solver_session.solution_visible)
        self.assertTrue(solver_session.solution_loaded_into_board)
        self.assertEqual(solver_session.board_source_label, "solver")

        solver_session.mark_player_controlled()
        self.assertFalse(solver_session.solution_visible)
        self.assertFalse(solver_session.solution_loaded_into_board)
        self.assertEqual(solver_session.board_source_label, "player")

    def test_show_solution_button_rect_stays_inside_sidebar(self) -> None:
        with patch.dict(
            os.environ,
            {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"},
            clear=False,
        ):
            pygame.init()
            try:
                puzzle = load_phase_a_puzzle()
                layout = build_board_layout(puzzle.puzzle_data)
                title_font = pygame.font.Font(None, 34)
                body_font = pygame.font.Font(None, 24)
                small_font = pygame.font.Font(None, 21)

                button_rect = show_solution_button_rect(
                    layout,
                    title_font,
                    body_font,
                    small_font,
                )

                self.assertTrue(layout.sidebar_rect.contains(button_rect))
                self.assertGreater(button_rect.width, 0)
                self.assertGreater(button_rect.height, 0)
            finally:
                pygame.quit()

    def test_phase_f_app_runs_headless_for_one_frame(self) -> None:
        with patch.dict(
            os.environ,
            {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"},
            clear=False,
        ):
            run_phase_f_app(max_frames=1)


if __name__ == "__main__":
    unittest.main()
