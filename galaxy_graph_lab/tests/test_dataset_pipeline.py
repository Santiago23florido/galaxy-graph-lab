from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from galaxy_graph_lab.core import dataset as dataset_module
from galaxy_graph_lab.core import (
    BoardSpec,
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_HARD,
    GENERATION_DIFFICULTY_MEDIUM,
    PuzzleGenerationRequest,
    difficulty_profile_for,
    generate_dataset,
    generate_instance,
    load_instance,
    save_instance,
    solve_dataset,
)


class DataSetPipelineTests(unittest.TestCase):
    def test_generate_instance_can_be_saved_and_loaded(self) -> None:
        request = PuzzleGenerationRequest(
            difficulty=GENERATION_DIFFICULTY_EASY,
            grid_size=BoardSpec(rows=5, cols=5),
            random_seed=0,
            max_generation_retries=64,
        )

        generation_result = generate_instance(
            request,
            instance_id="galaxy_easy_5x5_001",
            base_seed=0,
            seed_sweep=8,
        )

        self.assertTrue(generation_result.success)
        self.assertIsNotNone(generation_result.instance)

        with tempfile.TemporaryDirectory() as temporary_directory:
            instance_path = save_instance(
                generation_result.instance,
                Path(temporary_directory) / "galaxy_easy_5x5_001.json",
            )
            loaded_instance = load_instance(instance_path)

        self.assertEqual(loaded_instance.instance_id, "galaxy_easy_5x5_001")
        self.assertEqual(loaded_instance.requested_difficulty, GENERATION_DIFFICULTY_EASY)
        self.assertEqual(loaded_instance.grid_size, BoardSpec(rows=5, cols=5))
        self.assertTrue(loaded_instance.difficulty_calibration.profile_match)
        self.assertEqual(loaded_instance.puzzle_data.board, BoardSpec(rows=5, cols=5))

    def test_generate_dataset_covers_every_allowed_grid_size_for_one_difficulty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            generation_result = generate_dataset(
                {
                    GENERATION_DIFFICULTY_EASY: 1,
                    GENERATION_DIFFICULTY_MEDIUM: 0,
                    GENERATION_DIFFICULTY_HARD: 0,
                },
                data_dir=temporary_directory,
                max_generation_retries=64,
                seed_sweep=8,
                base_seed=0,
            )

            self.assertTrue(generation_result.success)
            self.assertIsNotNone(generation_result.manifest_path)
            self.assertTrue(generation_result.manifest_path.exists())

            expected_sizes = set(
                difficulty_profile_for(GENERATION_DIFFICULTY_EASY).allowed_grid_sizes
            )
            generated_sizes = {
                load_instance(path).grid_size
                for path in generation_result.instance_paths
            }

        self.assertEqual(generated_sizes, expected_sizes)
        self.assertEqual(
            generation_result.instances_by_difficulty[GENERATION_DIFFICULTY_EASY],
            len(expected_sizes),
        )

    def test_seed_attempts_expand_into_a_unique_dispersed_budget(self) -> None:
        seeds = dataset_module._seed_attempts(
            base_seed=0,
            seed_sweep=2,
            seed_block_count=3,
        )

        self.assertEqual(len(seeds), 6)
        self.assertEqual(seeds[0], 0)
        self.assertEqual(len(set(seeds)), 6)
        self.assertNotEqual(seeds, (0, 1, 2, 3, 4, 5))

    def test_solve_dataset_writes_cplex_style_result_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory) / "data"
            results_directory = Path(temporary_directory) / "res" / "cplex"

            generation_result = generate_dataset(
                {
                    GENERATION_DIFFICULTY_EASY: 1,
                    GENERATION_DIFFICULTY_MEDIUM: 0,
                    GENERATION_DIFFICULTY_HARD: 0,
                },
                data_dir=data_directory,
                max_generation_retries=64,
                seed_sweep=8,
                base_seed=0,
            )
            self.assertTrue(generation_result.success)

            solve_result = solve_dataset(
                data_dir=data_directory,
                results_dir=results_directory,
            )

            self.assertTrue(solve_result.success)
            self.assertIsNotNone(solve_result.summary_path)
            self.assertTrue(solve_result.summary_path.exists())
            self.assertEqual(
                len(solve_result.result_paths),
                len(generation_result.instance_paths),
            )
            self.assertIn(
                GENERATION_DIFFICULTY_EASY,
                solve_result.average_solve_time_by_difficulty,
            )

            for result_path in solve_result.result_paths:
                contents = result_path.read_text(encoding="utf-8")
                self.assertIn("solveTime=", contents)
                self.assertIn("isOptimal=", contents)


if __name__ == "__main__":
    unittest.main()
