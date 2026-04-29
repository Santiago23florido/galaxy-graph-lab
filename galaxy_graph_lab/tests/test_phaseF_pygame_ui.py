from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import pygame

from galaxy_graph_lab.core import (
    BoardSpec,
    Cell,
    CenterSpec,
    GalaxyAssignment,
    PuzzleData,
    PuzzleSolveResult,
    validate_assignment,
)
from galaxy_graph_lab.ui.app import (
    _window_size_from_event,
    request_solution_for_current_board,
    restore_manual_board_state,
    run_phase_f_app,
)
from galaxy_graph_lab.ui.debug_tools import (
    comparison_by_cell,
    comparison_counts,
    component_index_by_cell,
)
from galaxy_graph_lab.ui.game_state import EditablePuzzleState
from galaxy_graph_lab.ui.puzzle_loader import load_phase_a_puzzle
from galaxy_graph_lab.ui.renderer import (
    build_board_layout,
    info_panel_rect,
    menu_button_rect,
    restore_manual_button_rect,
    return_home_button_rect,
    show_solution_button_rect,
)
from galaxy_graph_lab.ui.solver_session import SolverSessionState


class PhaseFPygameUiTests(unittest.TestCase):
    def test_window_size_from_event_reads_videoresize_fields(self) -> None:
        event = pygame.event.Event(
            pygame.VIDEORESIZE,
            {"w": 1280, "h": 820, "size": (1280, 820)},
        )
        surface = pygame.Surface((320, 240))

        self.assertEqual(_window_size_from_event(event, surface), (1280, 820))

    def test_window_size_from_event_reads_windowresized_fields(self) -> None:
        window_resized = getattr(pygame, "WINDOWRESIZED", pygame.USEREVENT)
        event = pygame.event.Event(window_resized, {"x": 1920, "y": 1080})
        surface = pygame.Surface((320, 240))

        self.assertEqual(_window_size_from_event(event, surface), (1920, 1080))

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

    def test_comparison_by_cell_ignores_unselected_cells_by_default(self) -> None:
        comparison_lookup = comparison_by_cell(
            {Cell(0, 0): "A"},
            {Cell(0, 0): "A", Cell(0, 1): "B"},
        )

        self.assertEqual(dict(comparison_lookup), {Cell(0, 0): True})

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
        self.assertEqual(solver_session.board_mode_label, "solver-loaded")

        solver_session.mark_manual_edit()
        self.assertEqual(solver_session.board_mode_label, "mixed")

        solver_session.mark_player_controlled()
        self.assertFalse(solver_session.solution_visible)
        self.assertFalse(solver_session.solution_loaded_into_board)
        self.assertEqual(solver_session.board_mode_label, "manual")

    def test_comparison_reference_uses_manual_snapshot_while_solver_board_is_visible(self) -> None:
        solver_session = SolverSessionState()
        current_assignment = {Cell(0, 0): "A", Cell(0, 1): "A"}
        snapshot_assignment = {Cell(0, 0): "A"}

        solver_session.capture_manual_snapshot(snapshot_assignment)
        solver_session.mark_solution_loaded()

        comparison_reference = solver_session.comparison_reference_assignment_by_cell(
            current_assignment,
        )

        self.assertEqual(dict(comparison_reference), snapshot_assignment)

    def test_solver_session_restores_manual_snapshot(self) -> None:
        solver_session = SolverSessionState()
        snapshot = {Cell(0, 0): "A", Cell(0, 1): "B"}

        solver_session.capture_manual_snapshot(snapshot)
        solver_session.mark_solution_loaded()

        restored_snapshot = solver_session.restore_manual_snapshot()

        self.assertEqual(dict(restored_snapshot), snapshot)
        self.assertEqual(solver_session.board_mode_label, "manual")
        self.assertFalse(solver_session.can_restore_manual_snapshot)

    def test_solver_session_handles_backend_unavailable_result(self) -> None:
        solver_session = SolverSessionState()
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=1, cols=1),
            (CenterSpec.from_coordinates("A", 0, 0),),
        )
        unavailable_result = PuzzleSolveResult(
            success=False,
            backend_name="exact_flow",
            status_code=-2,
            status_label="backend_unavailable",
            message="Solver unavailable",
            assignment=None,
            objective_value=None,
            mip_gap=None,
            mip_node_count=None,
        )

        with patch(
            "galaxy_graph_lab.ui.solver_session.solve_puzzle",
            return_value=unavailable_result,
        ):
            result = solver_session.request_solution(puzzle_data)

        self.assertIs(result, unavailable_result)
        self.assertEqual(solver_session.solver_status_label, "backend_unavailable")
        self.assertEqual(solver_session.solver_message, "Solver unavailable")
        self.assertFalse(solver_session.solution_loaded_into_board)
        self.assertEqual(solver_session.board_mode_label, "manual")

    def test_request_solution_for_current_board_loads_a_valid_solver_assignment(self) -> None:
        puzzle_data = PuzzleData.from_specs(
            BoardSpec(rows=3, cols=3),
            [
                CenterSpec.from_coordinates("A", 0, 1),
                CenterSpec.from_coordinates("B", 1.5, 1),
            ],
        )
        game_state = EditablePuzzleState.from_center_ids(("A", "B"))
        solver_session = SolverSessionState()
        game_state.replace_assignments({Cell(0, 0): "A", Cell(1, 0): "A"})

        solved = request_solution_for_current_board(
            puzzle_data,
            game_state,
            solver_session,
        )

        self.assertTrue(solved)
        self.assertTrue(solver_session.solution_loaded_into_board)
        self.assertEqual(solver_session.solver_status_label, "solved")
        self.assertEqual(solver_session.solver_result.solution_mode, "guided_min_mismatch")
        validation = validate_assignment(puzzle_data, game_state.candidate_assignment())
        self.assertTrue(validation.is_valid)
        self.assertEqual(game_state.assigned_center_by_cell[Cell(1, 0)], "B")
        self.assertTrue(solver_session.can_restore_manual_snapshot)

    def test_restore_manual_board_state_restores_the_snapshot(self) -> None:
        game_state = EditablePuzzleState.from_center_ids(("A", "B"))
        solver_session = SolverSessionState()
        original_assignment = {Cell(0, 0): "A"}
        game_state.replace_assignments({Cell(0, 0): "B"})
        solver_session.capture_manual_snapshot(original_assignment)
        solver_session.mark_solution_loaded()

        restored = restore_manual_board_state(game_state, solver_session)

        self.assertTrue(restored)
        self.assertEqual(dict(game_state.assigned_center_by_cell), original_assignment)
        self.assertEqual(solver_session.board_mode_label, "manual")
        self.assertFalse(solver_session.can_restore_manual_snapshot)

    def test_board_action_buttons_and_menu_stay_inside_window(self) -> None:
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
                restore_rect = restore_manual_button_rect(
                    layout,
                    title_font,
                    body_font,
                    small_font,
                )
                home_rect = return_home_button_rect(layout)
                menu_rect = menu_button_rect(layout)
                panel_rect = info_panel_rect(layout)

                window_rect = pygame.Rect(0, 0, layout.window_width, layout.window_height)
                self.assertTrue(window_rect.contains(button_rect))
                self.assertTrue(window_rect.contains(restore_rect))
                self.assertTrue(window_rect.contains(home_rect))
                self.assertTrue(window_rect.contains(menu_rect))
                self.assertTrue(window_rect.contains(panel_rect))
                self.assertGreater(button_rect.width, 0)
                self.assertGreater(button_rect.height, 0)
                self.assertGreater(restore_rect.width, 0)
                self.assertGreater(restore_rect.height, 0)
                self.assertGreater(home_rect.width, 0)
                self.assertGreater(menu_rect.width, 0)
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
