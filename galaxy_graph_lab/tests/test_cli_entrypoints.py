from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from galaxy_graph_lab.core import (
    BoardSpec,
    DATASET_SOLVE_BACKEND_ALL,
    EXACT_FLOW_SOLVER_BACKEND,
    HEURISTIC_ORBIT_SOLVER_BACKEND,
    PARALLEL_CALLBACK_SOLVER_BACKEND,
)
from galaxy_graph_lab.dataset_cli import main as dataset_cli_main
from galaxy_graph_lab.main import main as game_main


class CliEntrypointTests(unittest.TestCase):
    def test_game_main_defaults_to_exact_flow_backend(self) -> None:
        with patch.object(sys, "argv", ["galaxy"]):
            with patch("galaxy_graph_lab.main.run_phase_f_app") as run_app_mock:
                game_main()

        run_app_mock.assert_called_once_with(
            solver_backend=EXACT_FLOW_SOLVER_BACKEND
        )

    def test_game_main_forwards_selected_solver_backend(self) -> None:
        with patch.object(
            sys,
            "argv",
            ["galaxy", "--solver-backend", PARALLEL_CALLBACK_SOLVER_BACKEND],
        ):
            with patch("galaxy_graph_lab.main.run_phase_f_app") as run_app_mock:
                game_main()

        run_app_mock.assert_called_once_with(
            solver_backend=PARALLEL_CALLBACK_SOLVER_BACKEND
        )

    def test_game_main_accepts_heuristic_solver_backend(self) -> None:
        with patch.object(
            sys,
            "argv",
            ["galaxy", "--solver-backend", HEURISTIC_ORBIT_SOLVER_BACKEND],
        ):
            with patch("galaxy_graph_lab.main.run_phase_f_app") as run_app_mock:
                game_main()

        run_app_mock.assert_called_once_with(
            solver_backend=HEURISTIC_ORBIT_SOLVER_BACKEND
        )

    def test_dataset_cli_forwards_selected_solver_backend_mode(self) -> None:
        solve_result = SimpleNamespace(
            success=True,
            message="Dataset solved successfully.",
            results_dir=Path("/tmp/res"),
            summary_path=Path("/tmp/res/summary.json"),
            solver_backends=("exact_flow", "parallel_callback"),
            average_solve_time_by_backend={
                "exact_flow": 0.1,
                "parallel_callback": 0.2,
            },
            average_solve_time_by_difficulty={"easy": 0.15},
            average_solve_time_by_backend_and_difficulty={
                "exact_flow": {"easy": 0.1},
                "parallel_callback": {"easy": 0.2},
            },
        )

        with patch.object(
            sys,
            "argv",
            [
                "dataset-cli",
                "solve-dataset",
                "--solver-backend",
                "both",
            ],
        ):
            with patch(
                "galaxy_graph_lab.dataset_cli.solve_dataset",
                return_value=solve_result,
            ) as solve_dataset_mock:
                with patch("builtins.print"):
                    dataset_cli_main()

        solve_dataset_mock.assert_called_once_with(
            data_dir=unittest.mock.ANY,
            results_dir=unittest.mock.ANY,
            solver_backend="both",
        )

    def test_generate_dataset_uses_fixed_size_window_without_threshold_search(self) -> None:
        generation_result = SimpleNamespace(
            success=True,
            message="Dataset generated successfully.",
            data_dir=Path("/tmp/data"),
            manifest_path=Path("/tmp/data/manifest.json"),
            instances_by_difficulty={"easy": 100, "medium": 100, "hard": 100},
        )

        with patch.object(sys, "argv", ["dataset-cli", "generate-dataset"]):
            with patch(
                "galaxy_graph_lab.dataset_cli.generate_dataset",
                return_value=generation_result,
            ) as generate_dataset_mock:
                with patch("builtins.print"):
                    dataset_cli_main()

        generate_dataset_mock.assert_called_once()
        kwargs = generate_dataset_mock.call_args.kwargs
        self.assertEqual(kwargs["selection_solver_backend"], EXACT_FLOW_SOLVER_BACKEND)
        self.assertEqual(kwargs["dataset_instance_min_solve_time_seconds"], 0.0)
        self.assertEqual(
            kwargs["dimensions_by_difficulty"]["easy"],
            (
                BoardSpec(rows=7, cols=7),
                BoardSpec(rows=8, cols=8),
                BoardSpec(rows=9, cols=9),
                BoardSpec(rows=10, cols=10),
                BoardSpec(rows=11, cols=11),
            ),
        )
        self.assertEqual(
            kwargs["dimensions_by_difficulty"]["medium"],
            kwargs["dimensions_by_difficulty"]["easy"],
        )
        self.assertEqual(
            kwargs["dimensions_by_difficulty"]["hard"],
            kwargs["dimensions_by_difficulty"]["easy"],
        )

    def test_find_hard_threshold_cli_forwards_search_parameters(self) -> None:
        threshold_result = SimpleNamespace(
            success=True,
            message="Hard-threshold search completed.",
            data_dir=Path("/tmp/threshold"),
            manifest_path=Path("/tmp/threshold/manifest.json"),
            progress_log_path=Path("/tmp/threshold/progress.log"),
            instance_paths=(
                Path("/tmp/threshold/hard_threshold_7x7.json"),
            ),
            threshold_seconds=0.5,
            solver_backend=EXACT_FLOW_SOLVER_BACKEND,
            max_solved_grid_size=BoardSpec(rows=13, cols=13),
            max_solved_solve_time=0.3,
            first_exceeding_grid_size=BoardSpec(rows=14, cols=14),
            first_exceeding_solve_time=0.8,
        )

        with patch.object(
            sys,
            "argv",
            [
                "dataset-cli",
                "find-hard-threshold",
                "--threshold-seconds",
                "0.5",
                "--start-side",
                "7",
                "--max-side",
                "20",
            ],
        ):
            with patch(
                "galaxy_graph_lab.dataset_cli.find_hard_threshold_limit",
                return_value=threshold_result,
            ) as search_mock:
                with patch("builtins.print"):
                    dataset_cli_main()

        search_mock.assert_called_once_with(
            data_dir=unittest.mock.ANY,
            threshold_seconds=0.5,
            solver_backend=EXACT_FLOW_SOLVER_BACKEND,
            start_side=7,
            max_side=20,
            max_generation_retries=unittest.mock.ANY,
            seed_sweep=unittest.mock.ANY,
            seed_block_count=unittest.mock.ANY,
            base_seed=None,
            progress_callback=unittest.mock.ANY,
        )

    def test_dataset_cli_forwards_single_solver_backend_mode(self) -> None:
        solve_result = SimpleNamespace(
            success=True,
            message="Dataset solved successfully.",
            results_dir=Path("/tmp/res"),
            summary_path=Path("/tmp/res/summary.json"),
            solver_backends=(PARALLEL_CALLBACK_SOLVER_BACKEND,),
            average_solve_time_by_backend={PARALLEL_CALLBACK_SOLVER_BACKEND: 0.2},
            average_solve_time_by_difficulty={"easy": 0.2},
            average_solve_time_by_backend_and_difficulty={
                PARALLEL_CALLBACK_SOLVER_BACKEND: {"easy": 0.2}
            },
        )

        with patch.object(
            sys,
            "argv",
            [
                "dataset-cli",
                "solve-dataset",
                "--solver-backend",
                PARALLEL_CALLBACK_SOLVER_BACKEND,
            ],
        ):
            with patch(
                "galaxy_graph_lab.dataset_cli.solve_dataset",
                return_value=solve_result,
            ) as solve_dataset_mock:
                with patch("builtins.print"):
                    dataset_cli_main()

        solve_dataset_mock.assert_called_once_with(
            data_dir=unittest.mock.ANY,
            results_dir=unittest.mock.ANY,
            solver_backend=PARALLEL_CALLBACK_SOLVER_BACKEND,
        )

    def test_dataset_cli_forwards_all_solver_backend_mode(self) -> None:
        solve_result = SimpleNamespace(
            success=True,
            message="Dataset solved successfully.",
            results_dir=Path("/tmp/res"),
            summary_path=Path("/tmp/res/summary.json"),
            solver_backends=(
                EXACT_FLOW_SOLVER_BACKEND,
                PARALLEL_CALLBACK_SOLVER_BACKEND,
                HEURISTIC_ORBIT_SOLVER_BACKEND,
            ),
            average_solve_time_by_backend={
                EXACT_FLOW_SOLVER_BACKEND: 0.1,
                PARALLEL_CALLBACK_SOLVER_BACKEND: 0.2,
                HEURISTIC_ORBIT_SOLVER_BACKEND: 0.3,
            },
            average_solve_time_by_difficulty={"easy": 0.2},
            average_solve_time_by_backend_and_difficulty={
                EXACT_FLOW_SOLVER_BACKEND: {"easy": 0.1},
                PARALLEL_CALLBACK_SOLVER_BACKEND: {"easy": 0.2},
                HEURISTIC_ORBIT_SOLVER_BACKEND: {"easy": 0.3},
            },
        )

        with patch.object(
            sys,
            "argv",
            [
                "dataset-cli",
                "solve-dataset",
                "--solver-backend",
                DATASET_SOLVE_BACKEND_ALL,
            ],
        ):
            with patch(
                "galaxy_graph_lab.dataset_cli.solve_dataset",
                return_value=solve_result,
            ) as solve_dataset_mock:
                with patch("builtins.print"):
                    dataset_cli_main()

        solve_dataset_mock.assert_called_once_with(
            data_dir=unittest.mock.ANY,
            results_dir=unittest.mock.ANY,
            solver_backend=DATASET_SOLVE_BACKEND_ALL,
        )


if __name__ == "__main__":
    unittest.main()
