from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from galaxy_graph_lab.core import dataset as dataset_module
from galaxy_graph_lab.core import (
    DATASET_SOLVE_BACKEND_ALL,
    BoardSpec,
    CenterSpec,
    Cell,
    DATASET_SOLVE_BACKEND_BOTH,
    DifficultyCalibration,
    EXACT_FLOW_SOLVER_BACKEND,
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_HARD,
    GENERATION_DIFFICULTY_MEDIUM,
    GalaxyAssignment,
    HEURISTIC_ORBIT_SOLVER_BACKEND,
    PARALLEL_CALLBACK_SOLVER_BACKEND,
    PuzzleGenerationRequest,
    PuzzleSolveResult,
    StoredPuzzleInstance,
    generate_dataset,
    generate_instance,
    load_instance,
    save_instance,
    solve_dataset,
    solve_instance,
)


class DataSetPipelineTests(unittest.TestCase):
    def _test_generation_dimensions(self):
        return {
            GENERATION_DIFFICULTY_EASY: (
                BoardSpec(rows=5, cols=5),
                BoardSpec(rows=7, cols=7),
            ),
            GENERATION_DIFFICULTY_MEDIUM: tuple(),
            GENERATION_DIFFICULTY_HARD: tuple(),
        }

    def _stored_instance(self) -> StoredPuzzleInstance:
        return StoredPuzzleInstance(
            instance_id="galaxy_easy_1x1_001",
            requested_difficulty=GENERATION_DIFFICULTY_EASY,
            grid_size=BoardSpec(rows=1, cols=1),
            centers=(CenterSpec.from_coordinates("g0", 0, 0),),
            generation_seed=0,
            generation_retry_count=0,
            center_type_by_center={"g0": "cell"},
            difficulty_calibration=DifficultyCalibration(
                requested_difficulty=GENERATION_DIFFICULTY_EASY,
                measured_difficulty=GENERATION_DIFFICULTY_EASY,
                measured_score=0.0,
                board_size_score=0.0,
                center_count_score=0.0,
                center_type_score=0.0,
                domain_overlap_score=0.0,
                solver_effort_score=0.0,
                average_domain_overlap=0.0,
                average_region_irregularity=0.0,
                average_non_rectangular_irregularity=0.0,
                max_region_irregularity=0.0,
                non_rectangular_region_count=0,
                overlap_within_target=True,
                irregularity_within_target=True,
                profile_match=True,
                message="ok",
            ),
        )

    def _stored_instance_for_board(
        self,
        difficulty: str,
        board: BoardSpec,
    ) -> StoredPuzzleInstance:
        center_row = board.rows // 2
        center_col = board.cols // 2
        return StoredPuzzleInstance(
            instance_id=f"galaxy_{difficulty}_{board.rows}x{board.cols}_001",
            requested_difficulty=difficulty,
            grid_size=board,
            centers=(CenterSpec.from_coordinates("g0", center_row, center_col),),
            generation_seed=0,
            generation_retry_count=0,
            center_type_by_center={"g0": "cell"},
            difficulty_calibration=DifficultyCalibration(
                requested_difficulty=difficulty,
                measured_difficulty=difficulty,
                measured_score=0.0,
                board_size_score=0.0,
                center_count_score=0.0,
                center_type_score=0.0,
                domain_overlap_score=0.0,
                solver_effort_score=0.0,
                average_domain_overlap=0.0,
                average_region_irregularity=0.0,
                average_non_rectangular_irregularity=0.0,
                max_region_irregularity=0.0,
                non_rectangular_region_count=0,
                overlap_within_target=True,
                irregularity_within_target=True,
                profile_match=True,
                message="ok",
            ),
        )

    def _single_cell_assignment(self) -> GalaxyAssignment:
        return GalaxyAssignment(
            assigned_center_by_cell={Cell(0, 0): "g0"},
            cells_by_center={"g0": (Cell(0, 0),)},
        )

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
                dimensions_by_difficulty=self._test_generation_dimensions(),
                selection_solver_backend=EXACT_FLOW_SOLVER_BACKEND,
                selection_min_solve_time_seconds=0.0,
                selection_max_candidate_attempts=8,
                dataset_instance_min_solve_time_seconds=0.0,
            )

            self.assertTrue(generation_result.success)
            self.assertIsNotNone(generation_result.manifest_path)
            self.assertTrue(generation_result.manifest_path.exists())

            expected_sizes = set(self._test_generation_dimensions()[GENERATION_DIFFICULTY_EASY])
            generated_sizes = {
                load_instance(path).grid_size
                for path in generation_result.instance_paths
            }

        self.assertEqual(generated_sizes, expected_sizes)
        self.assertEqual(
            generation_result.instances_by_difficulty[GENERATION_DIFFICULTY_EASY],
            len(expected_sizes),
        )

    def test_generate_dataset_discovers_reference_sizes_by_default(self) -> None:
        threshold_side = 17

        def fake_screen_candidate(**kwargs):
            difficulty = kwargs["difficulty"]
            grid_size = kwargs["grid_size"]
            instance_id = kwargs["instance_id"]
            seed_cursor = kwargs["seed_cursor"]
            next_seed_cursor = seed_cursor + 1
            if instance_id.startswith("reference_"):
                if difficulty != GENERATION_DIFFICULTY_HARD:
                    raise AssertionError("Only hard should define the reference threshold.")
                if grid_size.rows != threshold_side:
                    return dataset_module._ScreenedCandidateResult(
                        instance=None,
                        generation_result=None,
                        solve_result=None,
                        solve_time=None,
                        next_seed_cursor=next_seed_cursor,
                        candidate_attempt_count=1,
                    )
                return dataset_module._ScreenedCandidateResult(
                    instance=self._stored_instance_for_board(difficulty, grid_size),
                    generation_result=mock.Mock(
                        generation_seed_used=seed_cursor,
                        seed_attempt_count=1,
                    ),
                    solve_result=PuzzleSolveResult(
                        success=True,
                        backend_name=PARALLEL_CALLBACK_SOLVER_BACKEND,
                        status_code=1,
                        status_label="solved",
                        message="ok",
                        assignment=self._single_cell_assignment(),
                        objective_value=0.0,
                        mip_gap=0.0,
                        mip_node_count=0,
                    ),
                    solve_time=100.0,
                    next_seed_cursor=next_seed_cursor,
                    candidate_attempt_count=1,
                )

            return dataset_module._ScreenedCandidateResult(
                instance=self._stored_instance_for_board(difficulty, grid_size),
                generation_result=mock.Mock(
                    generation_seed_used=seed_cursor,
                    seed_attempt_count=1,
                ),
                solve_result=PuzzleSolveResult(
                    success=True,
                    backend_name=PARALLEL_CALLBACK_SOLVER_BACKEND,
                    status_code=1,
                    status_label="solved",
                    message="ok",
                    assignment=self._single_cell_assignment(),
                    objective_value=0.0,
                    mip_gap=0.0,
                    mip_node_count=0,
                ),
                solve_time=1.0,
                next_seed_cursor=next_seed_cursor,
                candidate_attempt_count=1,
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            with mock.patch.object(
                dataset_module,
                "_screen_grid_candidate",
                side_effect=fake_screen_candidate,
            ):
                generation_result = generate_dataset(
                    {
                        GENERATION_DIFFICULTY_EASY: 1,
                        GENERATION_DIFFICULTY_MEDIUM: 1,
                        GENERATION_DIFFICULTY_HARD: 1,
                    },
                    data_dir=temporary_directory,
                    reference_search_max_side=17,
                    clear_existing=True,
                )

        self.assertTrue(generation_result.success)
        self.assertEqual(
            generation_result.reference_grid_size_by_difficulty[GENERATION_DIFFICULTY_EASY],
            BoardSpec(rows=17, cols=17),
        )
        self.assertEqual(
            generation_result.reference_grid_size_by_difficulty[GENERATION_DIFFICULTY_MEDIUM],
            BoardSpec(rows=17, cols=17),
        )
        self.assertEqual(
            generation_result.reference_grid_size_by_difficulty[GENERATION_DIFFICULTY_HARD],
            BoardSpec(rows=17, cols=17),
        )
        self.assertEqual(
            generation_result.grid_sizes_by_difficulty[GENERATION_DIFFICULTY_EASY],
            (
                BoardSpec(rows=9, cols=9),
                BoardSpec(rows=11, cols=11),
                BoardSpec(rows=13, cols=13),
                BoardSpec(rows=15, cols=15),
                BoardSpec(rows=17, cols=17),
            ),
        )
        self.assertEqual(
            generation_result.grid_sizes_by_difficulty[GENERATION_DIFFICULTY_MEDIUM],
            (
                BoardSpec(rows=9, cols=9),
                BoardSpec(rows=11, cols=11),
                BoardSpec(rows=13, cols=13),
                BoardSpec(rows=15, cols=15),
                BoardSpec(rows=17, cols=17),
            ),
        )
        self.assertEqual(
            generation_result.grid_sizes_by_difficulty[GENERATION_DIFFICULTY_HARD],
            (
                BoardSpec(rows=9, cols=9),
                BoardSpec(rows=11, cols=11),
                BoardSpec(rows=13, cols=13),
                BoardSpec(rows=15, cols=15),
                BoardSpec(rows=17, cols=17),
            ),
        )
        self.assertEqual(len(generation_result.instance_paths), 15)

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
                dimensions_by_difficulty=self._test_generation_dimensions(),
                selection_solver_backend=EXACT_FLOW_SOLVER_BACKEND,
                selection_min_solve_time_seconds=0.0,
                selection_max_candidate_attempts=8,
                dataset_instance_min_solve_time_seconds=0.0,
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
                self.assertEqual(result_path.parent.name, EXACT_FLOW_SOLVER_BACKEND)

    def test_solve_instance_forwards_selected_backend(self) -> None:
        instance = self._stored_instance()
        solve_result = PuzzleSolveResult(
            success=False,
            backend_name=PARALLEL_CALLBACK_SOLVER_BACKEND,
            status_code=-2,
            status_label="backend_unavailable",
            message="missing callback solver",
            assignment=None,
            objective_value=None,
            mip_gap=None,
            mip_node_count=None,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory) / "data"
            results_directory = Path(temporary_directory) / "res"
            instance_path = save_instance(instance, data_directory / "galaxy_easy_1x1_001.json")

            with mock.patch.object(
                dataset_module,
                "solve_puzzle",
                return_value=solve_result,
            ) as solve_puzzle_mock:
                record = solve_instance(
                    instance,
                    instance_path=instance_path,
                    results_dir=results_directory,
                    solver_backend=PARALLEL_CALLBACK_SOLVER_BACKEND,
                )

        solve_puzzle_mock.assert_called_once()
        called_puzzle_data = solve_puzzle_mock.call_args.args[0]
        self.assertEqual(called_puzzle_data.board, instance.puzzle_data.board)
        self.assertEqual(
            solve_puzzle_mock.call_args.kwargs["backend"],
            PARALLEL_CALLBACK_SOLVER_BACKEND,
        )
        self.assertEqual(record.solve_result.backend_name, PARALLEL_CALLBACK_SOLVER_BACKEND)
        self.assertEqual(
            record.result_path.parent.name,
            PARALLEL_CALLBACK_SOLVER_BACKEND,
        )
        self.assertEqual(
            record.result_path.name,
            "galaxy_easy_1x1_001.txt",
        )

    def test_solve_dataset_can_run_both_backends(self) -> None:
        instance = self._stored_instance()

        def fake_solve_puzzle(puzzle_data, *, backend, **_kwargs):
            return PuzzleSolveResult(
                success=True,
                backend_name=backend,
                status_code=1,
                status_label="solved",
                message="ok",
                assignment=self._single_cell_assignment(),
                objective_value=0.0,
                mip_gap=0.0,
                mip_node_count=0,
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory) / "data"
            results_directory = Path(temporary_directory) / "res"
            save_instance(instance, data_directory / "galaxy_easy_1x1_001.json")

            with mock.patch.object(
                dataset_module,
                "solve_puzzle",
                side_effect=fake_solve_puzzle,
            ):
                solve_result = solve_dataset(
                    data_dir=data_directory,
                    results_dir=results_directory,
                    solver_backend=DATASET_SOLVE_BACKEND_BOTH,
                )

                self.assertTrue(
                    solve_result.summary_path is not None
                    and solve_result.summary_path.exists()
                )
                self.assertEqual(
                    set(solve_result.backend_summary_paths),
                    {EXACT_FLOW_SOLVER_BACKEND, PARALLEL_CALLBACK_SOLVER_BACKEND},
                )
                self.assertTrue(
                    all(path.exists() for path in solve_result.backend_summary_paths.values())
                )

        self.assertTrue(solve_result.success)
        self.assertEqual(
            solve_result.solver_backends,
            (EXACT_FLOW_SOLVER_BACKEND, PARALLEL_CALLBACK_SOLVER_BACKEND),
        )
        self.assertEqual(len(solve_result.records), 2)
        self.assertEqual(len(solve_result.result_paths), 2)
        self.assertEqual(
            {record.solve_result.backend_name for record in solve_result.records},
            {EXACT_FLOW_SOLVER_BACKEND, PARALLEL_CALLBACK_SOLVER_BACKEND},
        )
        self.assertEqual(
            set(solve_result.average_solve_time_by_backend),
            {EXACT_FLOW_SOLVER_BACKEND, PARALLEL_CALLBACK_SOLVER_BACKEND},
        )
        self.assertEqual(
            solve_result.status_counts_by_backend[EXACT_FLOW_SOLVER_BACKEND]["solved"],
            1,
        )
        self.assertEqual(
            solve_result.status_counts_by_backend[PARALLEL_CALLBACK_SOLVER_BACKEND]["solved"],
            1,
        )
        self.assertEqual(
            solve_result.comparison_summary["instances_solved_by_both"],
            1,
        )
        self.assertEqual(
            {str(path.relative_to(results_directory)) for path in solve_result.result_paths},
            {
                "exact_flow/galaxy_easy_1x1_001.txt",
                "parallel_callback/galaxy_easy_1x1_001.txt",
            },
        )

    def test_solve_dataset_supports_all_backend_mode(self) -> None:
        instance = self._stored_instance()

        def fake_solve_puzzle(puzzle_data, *, backend, **_kwargs):
            return PuzzleSolveResult(
                success=True,
                backend_name=backend,
                status_code=1,
                status_label="solved",
                message="ok",
                assignment=self._single_cell_assignment(),
                objective_value=0.0,
                mip_gap=0.0,
                mip_node_count=0,
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory) / "data"
            results_directory = Path(temporary_directory) / "res"
            save_instance(instance, data_directory / "galaxy_easy_1x1_001.json")

            with mock.patch.object(
                dataset_module,
                "solve_puzzle",
                side_effect=fake_solve_puzzle,
            ):
                solve_result = solve_dataset(
                    data_dir=data_directory,
                    results_dir=results_directory,
                    solver_backend=DATASET_SOLVE_BACKEND_ALL,
                )

        self.assertTrue(solve_result.success)
        self.assertEqual(
            solve_result.solver_backends,
            (
                EXACT_FLOW_SOLVER_BACKEND,
                PARALLEL_CALLBACK_SOLVER_BACKEND,
                HEURISTIC_ORBIT_SOLVER_BACKEND,
            ),
        )
        self.assertEqual(len(solve_result.records), 3)
        self.assertEqual(
            set(solve_result.backend_summary_paths),
            {
                EXACT_FLOW_SOLVER_BACKEND,
                PARALLEL_CALLBACK_SOLVER_BACKEND,
                HEURISTIC_ORBIT_SOLVER_BACKEND,
            },
        )
        self.assertIn("pairwise", solve_result.comparison_summary)


if __name__ == "__main__":
    unittest.main()
