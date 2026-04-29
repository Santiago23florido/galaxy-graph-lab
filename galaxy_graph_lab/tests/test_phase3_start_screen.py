from __future__ import annotations

import unittest

from galaxy_graph_lab.core import (
    BoardSpec,
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_HARD,
)
from galaxy_graph_lab.ui.app import build_generated_ui_puzzle
from galaxy_graph_lab.ui.start_screen import (
    StartScreenState,
    apply_start_screen_hit,
    build_generation_request_from_state,
    build_start_screen_layout,
    default_start_screen_state,
    difficulty_button_rects,
    generate_puzzle_button_rect,
    grid_size_button_rects,
    hit_test_start_screen,
)


class Phase3StartScreenTests(unittest.TestCase):
    def test_default_start_screen_state_uses_the_first_profile_and_size(self) -> None:
        state = default_start_screen_state()

        self.assertEqual(state.selected_difficulty, GENERATION_DIFFICULTY_EASY)
        self.assertEqual(state.selected_grid_size, BoardSpec(rows=5, cols=5))

    def test_selecting_a_new_difficulty_replaces_an_invalid_grid_size(self) -> None:
        state = StartScreenState(
            selected_difficulty=GENERATION_DIFFICULTY_EASY,
            selected_grid_size=BoardSpec(rows=5, cols=5),
        )

        state.select_difficulty(GENERATION_DIFFICULTY_HARD)

        self.assertEqual(state.selected_difficulty, GENERATION_DIFFICULTY_HARD)
        self.assertEqual(state.selected_grid_size, BoardSpec(rows=7, cols=7))

    def test_build_generation_request_uses_the_current_start_screen_selection(self) -> None:
        state = StartScreenState(
            selected_difficulty=GENERATION_DIFFICULTY_HARD,
            selected_grid_size=BoardSpec(rows=9, cols=9),
        )

        request = build_generation_request_from_state(
            state,
            random_seed=12,
            max_generation_retries=5,
        )

        self.assertEqual(request.difficulty, GENERATION_DIFFICULTY_HARD)
        self.assertEqual(request.grid_size, BoardSpec(rows=9, cols=9))
        self.assertEqual(request.random_seed, 12)
        self.assertEqual(request.max_generation_retries, 5)

    def test_hit_testing_identifies_difficulty_size_and_generate_controls(self) -> None:
        layout = build_start_screen_layout()
        state = default_start_screen_state()

        difficulty_hit = hit_test_start_screen(
            layout,
            state,
            difficulty_button_rects(layout)[GENERATION_DIFFICULTY_HARD].center,
        )
        size_hit = hit_test_start_screen(
            layout,
            state,
            grid_size_button_rects(layout, state)[BoardSpec(rows=7, cols=7)].center,
        )
        generate_hit = hit_test_start_screen(
            layout,
            state,
            generate_puzzle_button_rect(layout).center,
        )

        self.assertEqual(difficulty_hit.kind, "difficulty")
        self.assertEqual(difficulty_hit.difficulty, GENERATION_DIFFICULTY_HARD)
        self.assertEqual(size_hit.kind, "grid_size")
        self.assertEqual(size_hit.grid_size, BoardSpec(rows=7, cols=7))
        self.assertEqual(generate_hit.kind, "generate")

    def test_apply_start_screen_hit_updates_the_selection_state(self) -> None:
        layout = build_start_screen_layout()
        state = default_start_screen_state()

        apply_start_screen_hit(
            state,
            hit_test_start_screen(
                layout,
                state,
                difficulty_button_rects(layout)[GENERATION_DIFFICULTY_HARD].center,
            ),
        )

        self.assertEqual(state.selected_difficulty, GENERATION_DIFFICULTY_HARD)
        self.assertEqual(state.selected_grid_size, BoardSpec(rows=7, cols=7))

    def test_generate_button_builds_one_generated_ui_puzzle(self) -> None:
        state = default_start_screen_state()
        state.select_grid_size(BoardSpec(rows=7, cols=7))

        puzzle, message = build_generated_ui_puzzle(state, base_seed=0)

        self.assertIsNotNone(puzzle)
        self.assertEqual(message, "Puzzle generated successfully.")
        self.assertEqual(puzzle.puzzle_data.board, BoardSpec(rows=7, cols=7))
        self.assertEqual(puzzle.name, "Easy 7x7")


if __name__ == "__main__":
    unittest.main()
