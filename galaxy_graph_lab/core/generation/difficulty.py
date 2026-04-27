from __future__ import annotations

import math
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

from ..board import Cell
from ..milp import GalaxyAssignment
from ..model_data import PuzzleData
from ..solver_service import PuzzleSolveResult
from .profiles import (
    CENTER_TYPE_CELL,
    CENTER_TYPE_EDGE,
    CENTER_TYPE_VERTEX,
    DifficultyProfile,
)
from .request import (
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_HARD,
    GENERATION_DIFFICULTY_MEDIUM,
)


_CENTER_TYPE_COMPLEXITY = {
    CENTER_TYPE_CELL: 0.20,
    CENTER_TYPE_EDGE: 0.60,
    CENTER_TYPE_VERTEX: 1.00,
}
_MEASURED_DIFFICULTY_THRESHOLDS = (
    (0.28, GENERATION_DIFFICULTY_EASY),
    (0.55, GENERATION_DIFFICULTY_MEDIUM),
)


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _average(values: Iterable[float]) -> float:
    frozen_values = tuple(values)
    if not frozen_values:
        return 0.0
    return sum(frozen_values) / len(frozen_values)


def region_irregularity(cells: Collection[Cell]) -> float:
    """Measure how far one connected region is from filling its bounding box."""

    if not cells:
        return 0.0

    rows = [cell.row for cell in cells]
    cols = [cell.col for cell in cells]
    bounding_box_area = (
        (max(rows) - min(rows) + 1)
        * (max(cols) - min(cols) + 1)
    )
    return 1.0 - (len(cells) / bounding_box_area)


def _board_size_score(puzzle_data: PuzzleData) -> float:
    area = puzzle_data.board.rows * puzzle_data.board.cols
    return _clamp01((area - 25.0) / (81.0 - 25.0))


def _center_count_score(puzzle_data: PuzzleData) -> float:
    return _clamp01((len(puzzle_data.centers) - 2.0) / 10.0)


def _center_type_score(center_type_by_center: Mapping[str, str]) -> float:
    return _average(
        _CENTER_TYPE_COMPLEXITY[center_type]
        for center_type in center_type_by_center.values()
    )


def _domain_overlap_score(puzzle_data: PuzzleData) -> float:
    center_ids = tuple(center.id for center in puzzle_data.centers)
    overlaps: list[float] = []

    for index, center_id in enumerate(center_ids):
        cells_a = set(puzzle_data.admissible_cells_by_center[center_id])
        for other_center_id in center_ids[index + 1 :]:
            cells_b = set(puzzle_data.admissible_cells_by_center[other_center_id])
            denominator = min(len(cells_a), len(cells_b))
            if denominator == 0:
                continue
            overlaps.append(len(cells_a.intersection(cells_b)) / denominator)

    return _average(overlaps)


def _solver_effort_score(
    puzzle_data: PuzzleData,
    solve_result: PuzzleSolveResult,
) -> float:
    node_count = max(0, solve_result.mip_node_count or 0)
    reference_nodes = max(8.0, float(len(puzzle_data.cells) * len(puzzle_data.centers)))
    node_score = 0.0
    if node_count > 0:
        node_score = math.log1p(node_count) / math.log1p(reference_nodes)

    mode_bonus = 0.0
    if solve_result.solution_mode == "guided_min_mismatch":
        mode_bonus = 0.12

    return _clamp01(node_score + mode_bonus)


def _measured_difficulty_for_score(score: float) -> str:
    for threshold, difficulty in _MEASURED_DIFFICULTY_THRESHOLDS:
        if score < threshold:
            return difficulty
    return GENERATION_DIFFICULTY_HARD


def _irregularity_values(
    assignment: GalaxyAssignment,
) -> tuple[float, ...]:
    return tuple(
        region_irregularity(cells)
        for cells in assignment.cells_by_center.values()
    )


def _average_non_rectangular_irregularity(irregularities: tuple[float, ...]) -> float:
    non_rectangular_values = tuple(
        irregularity
        for irregularity in irregularities
        if irregularity > 1e-9
    )
    return _average(non_rectangular_values)


def _value_in_range(value: float, lower: float, upper: float, *, tolerance: float) -> bool:
    return (lower - tolerance) <= value <= (upper + tolerance)


@dataclass(frozen=True, slots=True)
class DifficultyCalibration:
    """Measured difficulty report for one certified generated puzzle."""

    requested_difficulty: str
    measured_difficulty: str
    measured_score: float
    board_size_score: float
    center_count_score: float
    center_type_score: float
    domain_overlap_score: float
    solver_effort_score: float
    average_domain_overlap: float
    average_region_irregularity: float
    average_non_rectangular_irregularity: float
    max_region_irregularity: float
    non_rectangular_region_count: int
    overlap_within_target: bool
    irregularity_within_target: bool
    profile_match: bool
    message: str


def calibrate_generated_puzzle_difficulty(
    puzzle_data: PuzzleData,
    assignment: GalaxyAssignment,
    center_type_by_center: Mapping[str, str],
    solve_result: PuzzleSolveResult,
    requested_profile: DifficultyProfile,
) -> DifficultyCalibration:
    """Measure and classify one certified puzzle against the requested profile."""

    board_size_score = _board_size_score(puzzle_data)
    center_count_score = _center_count_score(puzzle_data)
    center_type_score = _center_type_score(center_type_by_center)
    domain_overlap_score = _domain_overlap_score(puzzle_data)
    solver_effort_score = _solver_effort_score(puzzle_data, solve_result)

    measured_score = (
        (0.20 * board_size_score)
        + (0.35 * center_count_score)
        + (0.20 * center_type_score)
        + (0.15 * domain_overlap_score)
        + (0.10 * solver_effort_score)
    )
    measured_difficulty = _measured_difficulty_for_score(measured_score)

    irregularities = _irregularity_values(assignment)
    non_rectangular_region_count = sum(
        1 for irregularity in irregularities if irregularity > 1e-9
    )
    average_region_irregularity = _average(irregularities)
    average_non_rectangular_irregularity = _average_non_rectangular_irregularity(
        irregularities
    )
    max_region_irregularity = max(irregularities, default=0.0)

    overlap_within_target = _value_in_range(
        domain_overlap_score,
        requested_profile.overlap_target_range.min_ratio,
        requested_profile.overlap_target_range.max_ratio,
        tolerance=0.08,
    )

    if requested_profile.min_non_rectangular_regions == 0:
        irregularity_within_target = _value_in_range(
            average_region_irregularity,
            requested_profile.irregularity_target_range.min_ratio,
            requested_profile.irregularity_target_range.max_ratio,
            tolerance=0.05,
        )
    else:
        irregularity_within_target = (
            non_rectangular_region_count >= requested_profile.min_non_rectangular_regions
            and _value_in_range(
                average_non_rectangular_irregularity,
                requested_profile.irregularity_target_range.min_ratio,
                requested_profile.irregularity_target_range.max_ratio,
                tolerance=0.08,
            )
        )

    profile_match = (
        measured_difficulty == requested_profile.difficulty
        and overlap_within_target
        and irregularity_within_target
    )

    if profile_match:
        message = "Difficulty calibration matched the requested profile."
    else:
        message = (
            "Difficulty calibration mismatch: "
            f"requested {requested_profile.difficulty}, "
            f"measured {measured_difficulty}, "
            f"overlap={domain_overlap_score:.3f}, "
            f"non_rectangular_regions={non_rectangular_region_count}, "
            f"non_rectangular_irregularity={average_non_rectangular_irregularity:.3f}."
        )

    return DifficultyCalibration(
        requested_difficulty=requested_profile.difficulty,
        measured_difficulty=measured_difficulty,
        measured_score=measured_score,
        board_size_score=board_size_score,
        center_count_score=center_count_score,
        center_type_score=center_type_score,
        domain_overlap_score=domain_overlap_score,
        solver_effort_score=solver_effort_score,
        average_domain_overlap=domain_overlap_score,
        average_region_irregularity=average_region_irregularity,
        average_non_rectangular_irregularity=average_non_rectangular_irregularity,
        max_region_irregularity=max_region_irregularity,
        non_rectangular_region_count=non_rectangular_region_count,
        overlap_within_target=overlap_within_target,
        irregularity_within_target=irregularity_within_target,
        profile_match=profile_match,
        message=message,
    )


__all__ = [
    "DifficultyCalibration",
    "calibrate_generated_puzzle_difficulty",
    "region_irregularity",
]
