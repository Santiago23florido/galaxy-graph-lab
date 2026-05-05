from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from galaxy_graph_lab.core import (
    BoardSpec,
    CenterSpec,
    DifficultyCalibration,
    EXACT_FLOW_SOLVER_BACKEND,
    GalaxyAssignment,
    GENERATION_DIFFICULTY_EASY,
    PuzzleGenerationRequest,
    PuzzleSolveResult,
)
from galaxy_graph_lab.core.generation.certification import PuzzleCertificationResult
from galaxy_graph_lab.core.generation.service import GeneratedPuzzle, PuzzleGenerationResult
from galaxy_graph_lab.core.validators import validate_assignment
from galaxy_graph_lab.ui.game_cache import prepare_generated_puzzle_cache


class GameCacheTests(unittest.TestCase):
    def _single_center_full_board_assignment(self) -> GalaxyAssignment:
        from galaxy_graph_lab.core import Cell

        cells = tuple(Cell(row, col) for row in range(5) for col in range(5))
        return GalaxyAssignment(
            assigned_center_by_cell={cell: "g0" for cell in cells},
            cells_by_center={"g0": cells},
        )

    def _generation_result(self) -> PuzzleGenerationResult:
        board = BoardSpec(rows=5, cols=5)
        centers = (CenterSpec.from_coordinates("g0", 2, 2),)
        from galaxy_graph_lab.core import PuzzleData

        puzzle_data = PuzzleData.from_specs(board, centers)
        assignment = self._single_center_full_board_assignment()
        validation = validate_assignment(puzzle_data, assignment.cells_by_center)
        solve_result = PuzzleSolveResult(
            success=True,
            backend_name=EXACT_FLOW_SOLVER_BACKEND,
            status_code=1,
            status_label="solved",
            message="Solution found.",
            assignment=assignment,
            objective_value=0.0,
            mip_gap=0.0,
            mip_node_count=0,
        )
        certification = PuzzleCertificationResult(
            success=True,
            message="Puzzle generated successfully.",
            constructive_validation=validation,
            solve_result=solve_result,
            certified_validation=validation,
        )
        generated_puzzle = GeneratedPuzzle(
            name="Easy 5x5",
            puzzle_data=puzzle_data,
            constructive_assignment={"g0": assignment.cells_by_center["g0"]},
            certified_assignment=assignment,
            center_type_by_center={"g0": "cell"},
        )
        return PuzzleGenerationResult(
            success=True,
            status_code=1,
            status_label="generated",
            message="Puzzle generated successfully.",
            request=PuzzleGenerationRequest(
                difficulty=GENERATION_DIFFICULTY_EASY,
                grid_size=board,
                random_seed=0,
                max_generation_retries=64,
            ),
            profile=None,
            puzzle=generated_puzzle,
            retry_count=0,
            random_seed_used=0,
            placement=None,
            certification=certification,
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

    def test_prepare_generated_puzzle_cache_reuses_existing_solution(self) -> None:
        generation_result = self._generation_result()

        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory) / "data"
            results_dir = Path(temporary_directory) / "res"

            stored_instance, cached_result = prepare_generated_puzzle_cache(
                generation_result,
                solver_backend=EXACT_FLOW_SOLVER_BACKEND,
                data_dir=data_dir,
                results_dir=results_dir,
            )

            self.assertIsNotNone(cached_result)
            self.assertTrue((data_dir / f"{stored_instance.instance_id}.json").exists())
            self.assertTrue(
                (
                    results_dir
                    / EXACT_FLOW_SOLVER_BACKEND
                    / f"{stored_instance.instance_id}.json"
                ).exists()
            )

            with patch("galaxy_graph_lab.ui.game_cache.solve_puzzle") as solve_puzzle_mock:
                _, reused_result = prepare_generated_puzzle_cache(
                    generation_result,
                    solver_backend="parallel_callback",
                    data_dir=data_dir,
                    results_dir=results_dir,
                )

            solve_puzzle_mock.assert_not_called()
            self.assertIsNotNone(reused_result)
            self.assertEqual(reused_result.backend_name, EXACT_FLOW_SOLVER_BACKEND)

    def test_prepare_generated_puzzle_cache_reuses_matching_dataset_instance(self) -> None:
        generation_result = self._generation_result()

        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory) / "data"
            results_dir = Path(temporary_directory) / "res"
            data_dir.mkdir(parents=True, exist_ok=True)
            (results_dir / EXACT_FLOW_SOLVER_BACKEND).mkdir(parents=True, exist_ok=True)

            generated_instance = generation_result.puzzle.puzzle_data
            from galaxy_graph_lab.core import StoredPuzzleInstance, save_instance

            shared_instance = StoredPuzzleInstance(
                instance_id="galaxy_easy_5x5_001",
                requested_difficulty=GENERATION_DIFFICULTY_EASY,
                grid_size=generation_result.request.grid_size,
                centers=generated_instance.centers,
                generation_seed=123,
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
            save_instance(shared_instance, data_dir / f"{shared_instance.instance_id}.json")
            (results_dir / EXACT_FLOW_SOLVER_BACKEND / f"{shared_instance.instance_id}.json").write_text(
                json.dumps(
                    {
                        "instance_id": shared_instance.instance_id,
                        "backend_name": EXACT_FLOW_SOLVER_BACKEND,
                        "status_code": 1,
                        "status_label": "solved",
                        "message": "cached",
                        "objective_value": 0.0,
                        "mip_gap": 0.0,
                        "mip_node_count": 0,
                        "solution_mode": "plain_exact",
                        "preferred_assignment_count": 0,
                        "matched_preference_count": None,
                        "mismatch_count": None,
                        "cells_by_center": {
                            "g0": [
                                {"row": row, "col": col}
                                for row in range(5)
                                for col in range(5)
                            ]
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            with patch("galaxy_graph_lab.ui.game_cache.solve_puzzle") as solve_puzzle_mock:
                reused_instance, reused_result = prepare_generated_puzzle_cache(
                    generation_result,
                    solver_backend=EXACT_FLOW_SOLVER_BACKEND,
                    data_dir=data_dir,
                    results_dir=results_dir,
                )

            solve_puzzle_mock.assert_not_called()
            self.assertEqual(reused_instance.instance_id, shared_instance.instance_id)
            self.assertIsNotNone(reused_result)


if __name__ == "__main__":
    unittest.main()
