from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from galaxy_graph_lab.core import PARALLEL_CALLBACK_SOLVER_BACKEND
from galaxy_graph_lab.dataset_cli import main as dataset_cli_main
from galaxy_graph_lab.main import main as game_main


class CliEntrypointTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
