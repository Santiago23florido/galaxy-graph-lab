"""Tests for the structured generation pipeline and solver certification."""

from __future__ import annotations

import random
import unittest

from galaxy_graph_lab.core import (
    BoardSpec,
    CENTER_TYPE_CELL,
    CENTER_TYPE_EDGE,
    CENTER_TYPE_VERTEX,
    GENERATION_DIFFICULTY_HARD,
    GENERATION_DIFFICULTY_MEDIUM,
    PlacedCenterRegion,
    PuzzleGenerationRequest,
    RectangleRegion,
    CenterSpec,
    certify_generated_puzzle,
    close_candidate_partition,
    difficulty_profile_for,
    generate_puzzle,
    grow_candidate_regions,
    place_candidate_centers,
    validate_assignment,
)
from galaxy_graph_lab.core.model_data import PuzzleData


class GenerationPipelineTests(unittest.TestCase):
    def test_rectangle_regions_classify_cell_edge_and_vertex_centers(self) -> None:
        self.assertEqual(
            RectangleRegion(top=0, bottom=2, left=0, right=2).center_type,
            CENTER_TYPE_CELL,
        )
        self.assertEqual(
            RectangleRegion(top=0, bottom=2, left=0, right=1).center_type,
            CENTER_TYPE_EDGE,
        )
        self.assertEqual(
            RectangleRegion(top=0, bottom=1, left=0, right=1).center_type,
            CENTER_TYPE_VERTEX,
        )

    def test_rectangular_growth_and_partition_closure_build_a_valid_assignment(self) -> None:
        board = BoardSpec(rows=5, cols=5)
        regions = (
            PlacedCenterRegion(
                id="g0",
                rectangle=RectangleRegion(top=0, bottom=4, left=0, right=2),
                center=CenterSpec(id="g0", row_coord2=4, col_coord2=2),
                center_type=CENTER_TYPE_CELL,
            ),
            PlacedCenterRegion(
                id="g1",
                rectangle=RectangleRegion(top=0, bottom=4, left=3, right=4),
                center=CenterSpec(id="g1", row_coord2=4, col_coord2=7),
                center_type=CENTER_TYPE_EDGE,
            ),
        )

        grown_assignment = grow_candidate_regions(board, regions)
        closure = close_candidate_partition(board, regions, grown_assignment)

        self.assertTrue(closure.success)
        self.assertIsNotNone(closure.cells_by_center)

        puzzle_data = PuzzleData.from_specs(board, tuple(region.center for region in regions))
        validation = validate_assignment(puzzle_data, closure.cells_by_center)
        self.assertTrue(validation.is_valid)

        certification = certify_generated_puzzle(puzzle_data, closure.cells_by_center)
        self.assertTrue(certification.success)
        self.assertTrue(certification.constructive_validation.is_valid)
        self.assertTrue(certification.certified_validation.is_valid)

    def test_center_placement_returns_a_profile_bounded_layout(self) -> None:
        board = BoardSpec(rows=7, cols=7)
        profile = difficulty_profile_for(GENERATION_DIFFICULTY_HARD)
        placement = place_candidate_centers(board, profile, random.Random(11))

        self.assertIsNotNone(placement)
        self.assertGreaterEqual(len(placement.regions), profile.min_center_count)
        self.assertLessEqual(len(placement.regions), profile.max_center_count)
        self.assertTrue(
            all(region.center_type in {CENTER_TYPE_CELL, CENTER_TYPE_EDGE, CENTER_TYPE_VERTEX}
                for region in placement.regions)
        )

    def test_generate_puzzle_returns_a_constructive_and_certified_puzzle(self) -> None:
        request = PuzzleGenerationRequest(
            difficulty=GENERATION_DIFFICULTY_MEDIUM,
            grid_size=BoardSpec(rows=7, cols=7),
            random_seed=19,
            max_generation_retries=4,
        )

        result = generate_puzzle(request)

        self.assertTrue(result.success)
        self.assertIsNotNone(result.placement)
        self.assertIsNotNone(result.certification)
        self.assertIsNotNone(result.puzzle)
        self.assertGreaterEqual(len(result.placement.regions), result.profile.min_center_count)
        self.assertLessEqual(len(result.placement.regions), result.profile.max_center_count)
        self.assertTrue(result.certification.success)

        constructive_validation = validate_assignment(
            result.puzzle.puzzle_data,
            result.puzzle.constructive_assignment,
        )
        certified_validation = validate_assignment(
            result.puzzle.puzzle_data,
            result.puzzle.certified_assignment.cells_by_center,
        )
        self.assertTrue(constructive_validation.is_valid)
        self.assertTrue(certified_validation.is_valid)


if __name__ == "__main__":
    unittest.main()
