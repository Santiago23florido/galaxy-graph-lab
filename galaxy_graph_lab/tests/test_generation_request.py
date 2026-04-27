"""Tests for the Phase 1 puzzle-generation request layer."""

from __future__ import annotations

import unittest

from galaxy_graph_lab.core import (
    BoardSpec,
    CENTER_TYPES,
    DifficultyProfile,
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_HARD,
    GENERATION_DIFFICULTY_MEDIUM,
    GENERATION_STATUS_GENERATED,
    PuzzleGenerationRequest,
    PuzzleGenerationResult,
    difficulty_profile_for,
    difficulty_profiles,
    generate_puzzle,
    solve_puzzle,
    validate_assignment,
)


class GenerationRequestTests(unittest.TestCase):
    def test_request_rejects_unknown_difficulty(self) -> None:
        with self.assertRaises(ValueError):
            PuzzleGenerationRequest(
                difficulty="impossible",
                grid_size=BoardSpec(rows=5, cols=5),
            )

    def test_request_rejects_non_positive_retry_budget(self) -> None:
        with self.assertRaises(ValueError):
            PuzzleGenerationRequest(
                difficulty=GENERATION_DIFFICULTY_EASY,
                grid_size=BoardSpec(rows=5, cols=5),
                max_generation_retries=0,
            )

    def test_request_rejects_grid_sizes_outside_the_difficulty_profile(self) -> None:
        with self.assertRaises(ValueError):
            PuzzleGenerationRequest(
                difficulty=GENERATION_DIFFICULTY_EASY,
                grid_size=BoardSpec(rows=9, cols=9),
            )

    def test_difficulty_profile_lookup_returns_structured_constraints(self) -> None:
        profile = difficulty_profile_for(GENERATION_DIFFICULTY_HARD)

        self.assertIsInstance(profile, DifficultyProfile)
        self.assertEqual(profile.difficulty, GENERATION_DIFFICULTY_HARD)
        self.assertEqual(
            profile.allowed_grid_sizes,
            (
                BoardSpec(rows=7, cols=7),
                BoardSpec(rows=9, cols=9),
            ),
        )
        self.assertEqual(
            {
                center_type
                for center_type in CENTER_TYPES
            },
            set(CENTER_TYPES),
        )
        self.assertAlmostEqual(
            profile.center_type_mix.cell_weight
            + profile.center_type_mix.edge_weight
            + profile.center_type_mix.vertex_weight,
            1.0,
        )
        self.assertTrue(profile.uniqueness_required)

    def test_difficulty_profiles_follow_the_stable_difficulty_order(self) -> None:
        self.assertEqual(
            tuple(profile.difficulty for profile in difficulty_profiles()),
            (
                GENERATION_DIFFICULTY_EASY,
                GENERATION_DIFFICULTY_MEDIUM,
                GENERATION_DIFFICULTY_HARD,
            ),
        )

    def test_generate_puzzle_returns_one_structured_placeholder_result(self) -> None:
        request = PuzzleGenerationRequest(
            difficulty=GENERATION_DIFFICULTY_MEDIUM,
            grid_size=BoardSpec(rows=7, cols=7),
            random_seed=17,
            max_generation_retries=9,
        )

        result = generate_puzzle(request)

        self.assertIsInstance(result, PuzzleGenerationResult)
        self.assertTrue(result.success)
        self.assertEqual(result.status_label, GENERATION_STATUS_GENERATED)
        self.assertEqual(result.message, "Puzzle generated successfully.")
        self.assertEqual(result.request, request)
        self.assertEqual(result.profile, request.difficulty_profile)
        self.assertLessEqual(result.retry_count, request.max_generation_retries)
        self.assertEqual(result.random_seed_used, 17)
        self.assertIsNotNone(result.puzzle)
        self.assertIsNotNone(result.placement)
        self.assertIsNotNone(result.certification)
        self.assertEqual(result.puzzle.puzzle_data.board, BoardSpec(rows=7, cols=7))
        self.assertEqual(result.puzzle.name, "Medium 7x7")

    def test_generated_puzzle_is_immediately_compatible_with_the_solver_stack(self) -> None:
        request = PuzzleGenerationRequest(
            difficulty=GENERATION_DIFFICULTY_EASY,
            grid_size=BoardSpec(rows=5, cols=5),
        )

        generation_result = generate_puzzle(request)
        self.assertTrue(generation_result.success)

        solve_result = solve_puzzle(generation_result.puzzle.puzzle_data)
        self.assertTrue(solve_result.success)

        validation_result = validate_assignment(
            generation_result.puzzle.puzzle_data,
            solve_result.assignment.cells_by_center,
        )
        self.assertTrue(validation_result.is_valid)


if __name__ == "__main__":
    unittest.main()
