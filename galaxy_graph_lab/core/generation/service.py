from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from random import Random
from time import perf_counter
from types import MappingProxyType

from ..board import Cell
from ..milp import GalaxyAssignment
from ..model_data import PuzzleData
from .certification import PuzzleCertificationResult, certify_generated_puzzle
from .center_placement import CenterPlacementResult, place_candidate_centers
from .difficulty import (
    DifficultyCalibration,
    average_domain_overlap,
    calibrate_generated_puzzle_difficulty,
)
from .partition_closure import close_candidate_partition
from .preference_shaping import build_preferred_assignment_by_cell
from .profiles import DifficultyProfile
from .region_growth import grow_candidate_regions
from .request import PuzzleGenerationRequest


GENERATION_STATUS_GENERATED = "generated"
GENERATION_STATUS_ERROR = "generation_error"


@dataclass(frozen=True, slots=True)
class GeneratedPuzzle:
    """Structured puzzle payload returned by the generation pipeline."""

    name: str
    puzzle_data: PuzzleData
    constructive_assignment: Mapping[str, tuple[Cell, ...]]
    certified_assignment: GalaxyAssignment
    center_type_by_center: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class PuzzleGenerationResult:
    """Stable top-level result returned by the public generation entrypoint."""

    success: bool
    status_code: int
    status_label: str
    message: str
    request: PuzzleGenerationRequest
    profile: DifficultyProfile | None
    puzzle: GeneratedPuzzle | None
    retry_count: int
    random_seed_used: int | None
    placement: CenterPlacementResult | None
    certification: PuzzleCertificationResult | None
    difficulty_calibration: DifficultyCalibration | None


def _build_generated_puzzle(
    request: PuzzleGenerationRequest,
    placement: CenterPlacementResult,
    constructive_assignment: Mapping[str, tuple[Cell, ...]],
    certification: PuzzleCertificationResult,
) -> GeneratedPuzzle:
    if certification.solve_result.assignment is None:
        raise ValueError("Certified puzzle requires one solver assignment.")

    puzzle_data = PuzzleData.from_specs(request.grid_size, placement.centers)
    puzzle_name = (
        f"{request.difficulty.title()} "
        f"{request.grid_size.rows}x{request.grid_size.cols}"
    )
    return GeneratedPuzzle(
        name=puzzle_name,
        puzzle_data=puzzle_data,
        constructive_assignment=MappingProxyType(
            {
                center_id: tuple(cells)
                for center_id, cells in constructive_assignment.items()
            }
        ),
        certified_assignment=certification.solve_result.assignment,
        center_type_by_center=placement.center_type_by_center,
    )


def _overlap_screen_is_plausible(
    puzzle_data: PuzzleData,
    profile: DifficultyProfile,
) -> bool:
    overlap = average_domain_overlap(puzzle_data)
    tolerance = 0.18
    return (
        profile.overlap_target_range.min_ratio - tolerance
        <= overlap
        <= profile.overlap_target_range.max_ratio + tolerance
    )


def _should_retry_with_stronger_shaping(
    profile: DifficultyProfile,
    difficulty_calibration: DifficultyCalibration | None,
) -> bool:
    if difficulty_calibration is None:
        return False
    if profile.min_non_rectangular_regions <= 0:
        return False
    if difficulty_calibration.profile_match:
        return False
    return (
        difficulty_calibration.overlap_within_target
        and not difficulty_calibration.irregularity_within_target
    )


def _certify_with_guidance_levels(
    puzzle_data: PuzzleData,
    placement: CenterPlacementResult,
    constructive_assignment: Mapping[str, tuple[Cell, ...]],
    profile: DifficultyProfile,
    rng: Random,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[PuzzleCertificationResult, DifficultyCalibration | None]:
    if profile.min_non_rectangular_regions <= 0:
        certification_started_at = perf_counter()
        if progress_callback is not None:
            progress_callback("stage=certification mode=plain start")
        certification = certify_generated_puzzle(
            puzzle_data,
            constructive_assignment,
        )
        if progress_callback is not None:
            progress_callback(
                "stage=certification mode=plain "
                f"done in {perf_counter() - certification_started_at:.2f}s "
                f"success={certification.success}"
            )
        if not certification.success or certification.solve_result.assignment is None:
            return certification, None
        difficulty_calibration = calibrate_generated_puzzle_difficulty(
            puzzle_data,
            certification.solve_result.assignment,
            placement.center_type_by_center,
            certification.solve_result,
            profile,
        )
        return certification, difficulty_calibration

    guidance_levels = (
        (1.0, max(2, profile.min_non_rectangular_regions * 2)),
        (1.35, max(3, profile.min_non_rectangular_regions * 3)),
    )
    last_certification: PuzzleCertificationResult | None = None
    last_difficulty_calibration: DifficultyCalibration | None = None

    for aggressiveness, minimum_mismatches in guidance_levels:
        guidance_started_at = perf_counter()
        if progress_callback is not None:
            progress_callback(
                "stage=certification "
                f"mode=guided aggressiveness={aggressiveness:.2f} "
                f"minimum_mismatches={minimum_mismatches} start"
            )
        solver_guidance = build_preferred_assignment_by_cell(
            puzzle_data,
            placement,
            constructive_assignment,
            profile,
            rng,
            aggressiveness=aggressiveness,
        )
        certification = certify_generated_puzzle(
            puzzle_data,
            constructive_assignment,
            preferred_assignment_by_cell=solver_guidance.preferred_assignment_by_cell,
            avoid_assignment_by_cell=solver_guidance.avoid_assignment_by_cell,
            minimum_mismatches_against_avoid=(
                0
                if not solver_guidance.avoid_assignment_by_cell
                else minimum_mismatches
            ),
        )
        last_certification = certification
        if progress_callback is not None:
            progress_callback(
                "stage=certification "
                f"mode=guided aggressiveness={aggressiveness:.2f} "
                f"done in {perf_counter() - guidance_started_at:.2f}s "
                f"success={certification.success}"
            )
        if not certification.success or certification.solve_result.assignment is None:
            continue

        difficulty_calibration = calibrate_generated_puzzle_difficulty(
            puzzle_data,
            certification.solve_result.assignment,
            placement.center_type_by_center,
            certification.solve_result,
            profile,
        )
        last_difficulty_calibration = difficulty_calibration
        if difficulty_calibration.profile_match:
            return certification, difficulty_calibration
        if not _should_retry_with_stronger_shaping(profile, difficulty_calibration):
            return certification, difficulty_calibration

    if last_certification is None:
        raise ValueError("Expected at least one certification attempt.")
    return last_certification, last_difficulty_calibration


def _generate_one_attempt(
    request: PuzzleGenerationRequest,
    profile: DifficultyProfile,
    rng: Random,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[
    GeneratedPuzzle | None,
    CenterPlacementResult | None,
    PuzzleCertificationResult | None,
    DifficultyCalibration | None,
    str,
]:
    placement_started_at = perf_counter()
    if progress_callback is not None:
        progress_callback("stage=center_placement start")
    placement = place_candidate_centers(request.grid_size, profile, rng)
    if progress_callback is not None:
        progress_callback(
            "stage=center_placement "
            f"done in {perf_counter() - placement_started_at:.2f}s "
            f"success={placement is not None}"
        )
    if placement is None:
        return None, None, None, None, "Could not place centers for the selected profile."

    overlap_started_at = perf_counter()
    if progress_callback is not None:
        progress_callback("stage=overlap_screen start")
    placement_puzzle_data = PuzzleData.from_specs(request.grid_size, placement.centers)
    if not _overlap_screen_is_plausible(placement_puzzle_data, profile):
        if progress_callback is not None:
            progress_callback(
                "stage=overlap_screen "
                f"done in {perf_counter() - overlap_started_at:.2f}s success=false"
            )
        return (
            None,
            placement,
            None,
            None,
            "Center placement produced admissible-domain overlap far from the target profile.",
        )
    if progress_callback is not None:
        progress_callback(
            "stage=overlap_screen "
            f"done in {perf_counter() - overlap_started_at:.2f}s success=true"
        )

    growth_started_at = perf_counter()
    if progress_callback is not None:
        progress_callback("stage=region_growth start")
    grown_assignment = grow_candidate_regions(request.grid_size, placement.regions)
    if progress_callback is not None:
        progress_callback(
            "stage=region_growth "
            f"done in {perf_counter() - growth_started_at:.2f}s"
        )

    closure_started_at = perf_counter()
    if progress_callback is not None:
        progress_callback("stage=partition_closure start")
    closure = close_candidate_partition(
        request.grid_size,
        placement.regions,
        grown_assignment,
    )
    if progress_callback is not None:
        progress_callback(
            "stage=partition_closure "
            f"done in {perf_counter() - closure_started_at:.2f}s "
            f"success={closure.success}"
        )
    if not closure.success or closure.cells_by_center is None:
        return None, placement, None, None, closure.message

    puzzle_data = placement_puzzle_data
    if progress_callback is not None:
        progress_callback("stage=certification_pipeline start")
    certification, difficulty_calibration = _certify_with_guidance_levels(
        puzzle_data,
        placement,
        closure.cells_by_center,
        profile,
        rng,
        progress_callback=progress_callback,
    )
    if progress_callback is not None:
        progress_callback(
            f"stage=certification_pipeline done success={certification.success}"
        )
    if not certification.success:
        return None, placement, certification, None, certification.message

    if certification.solve_result.assignment is None:
        return None, placement, certification, None, "Solver did not return an assignment."

    if difficulty_calibration is None:
        difficulty_calibration = calibrate_generated_puzzle_difficulty(
            puzzle_data,
            certification.solve_result.assignment,
            placement.center_type_by_center,
            certification.solve_result,
            profile,
        )

    puzzle = _build_generated_puzzle(
        request,
        placement,
        closure.cells_by_center,
        certification,
    )
    message = certification.message
    if not difficulty_calibration.profile_match:
        message = (
            "Puzzle generated successfully. "
            f"Difficulty calibration note: {difficulty_calibration.message}"
        )
    return (
        puzzle,
        placement,
        certification,
        difficulty_calibration,
        message,
    )


def generate_puzzle(
    request: PuzzleGenerationRequest,
    *,
    profile_override: DifficultyProfile | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> PuzzleGenerationResult:
    """Build one puzzle instance through the public generation entrypoint."""

    profile = request.difficulty_profile if profile_override is None else profile_override
    rng = Random(request.random_seed)
    last_message = "The generator did not attempt any candidate."
    last_placement: CenterPlacementResult | None = None
    last_certification: PuzzleCertificationResult | None = None
    last_difficulty_calibration: DifficultyCalibration | None = None

    for attempt_index in range(request.max_generation_retries):
        if progress_callback is not None:
            progress_callback(
                f"generation_attempt={attempt_index + 1}/{request.max_generation_retries} start"
            )
        try:
            (
                puzzle,
                placement,
                certification,
                difficulty_calibration,
                message,
            ) = _generate_one_attempt(
                request,
                profile,
                rng,
                progress_callback=progress_callback,
            )
        except Exception as exc:
            last_message = f"The generator could not build a puzzle: {exc}."
            if progress_callback is not None:
                progress_callback(
                    f"generation_attempt={attempt_index + 1}/{request.max_generation_retries} "
                    f"exception={exc}"
                )
            continue

        last_message = message
        last_placement = placement
        last_certification = certification
        last_difficulty_calibration = difficulty_calibration
        if progress_callback is not None:
            progress_callback(
                f"generation_attempt={attempt_index + 1}/{request.max_generation_retries} "
                f"result={'success' if puzzle is not None else 'retry'}"
            )
        if puzzle is None:
            continue

        return PuzzleGenerationResult(
            success=True,
            status_code=0,
            status_label=GENERATION_STATUS_GENERATED,
            message=message,
            request=request,
            profile=profile,
            puzzle=puzzle,
            retry_count=attempt_index,
            random_seed_used=request.random_seed,
            placement=placement,
            certification=certification,
            difficulty_calibration=difficulty_calibration,
        )

    return PuzzleGenerationResult(
        success=False,
        status_code=-1,
        status_label=GENERATION_STATUS_ERROR,
        message=last_message,
        request=request,
        profile=profile,
        puzzle=None,
        retry_count=request.max_generation_retries,
        random_seed_used=request.random_seed,
        placement=last_placement,
        certification=last_certification,
        difficulty_calibration=last_difficulty_calibration,
    )


__all__ = [
    "GENERATION_STATUS_ERROR",
    "GENERATION_STATUS_GENERATED",
    "GeneratedPuzzle",
    "PuzzleGenerationResult",
    "generate_puzzle",
]
