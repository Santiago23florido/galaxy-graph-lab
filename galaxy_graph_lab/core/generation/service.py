from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from random import Random
from types import MappingProxyType

from ..board import Cell
from ..milp import GalaxyAssignment
from ..model_data import PuzzleData
from .certification import PuzzleCertificationResult, certify_generated_puzzle
from .center_placement import CenterPlacementResult, place_candidate_centers
from .partition_closure import close_candidate_partition
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


def _generate_one_attempt(
    request: PuzzleGenerationRequest,
    profile: DifficultyProfile,
    rng: Random,
) -> tuple[GeneratedPuzzle | None, CenterPlacementResult | None, PuzzleCertificationResult | None, str]:
    placement = place_candidate_centers(request.grid_size, profile, rng)
    if placement is None:
        return None, None, None, "Could not place centers for the selected profile."

    grown_assignment = grow_candidate_regions(request.grid_size, placement.regions)
    closure = close_candidate_partition(
        request.grid_size,
        placement.regions,
        grown_assignment,
    )
    if not closure.success or closure.cells_by_center is None:
        return None, placement, None, closure.message

    puzzle_data = PuzzleData.from_specs(request.grid_size, placement.centers)
    certification = certify_generated_puzzle(
        puzzle_data,
        closure.cells_by_center,
    )
    if not certification.success:
        return None, placement, certification, certification.message

    puzzle = _build_generated_puzzle(
        request,
        placement,
        closure.cells_by_center,
        certification,
    )
    return puzzle, placement, certification, certification.message


def generate_puzzle(request: PuzzleGenerationRequest) -> PuzzleGenerationResult:
    """Build one puzzle instance through the public generation entrypoint."""

    profile = request.difficulty_profile
    rng = Random(request.random_seed)
    last_message = "The generator did not attempt any candidate."
    last_placement: CenterPlacementResult | None = None
    last_certification: PuzzleCertificationResult | None = None

    for attempt_index in range(request.max_generation_retries):
        try:
            puzzle, placement, certification, message = _generate_one_attempt(
                request,
                profile,
                rng,
            )
        except Exception as exc:
            last_message = f"The generator could not build a puzzle: {exc}."
            continue

        last_message = message
        last_placement = placement
        last_certification = certification
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
    )


__all__ = [
    "GENERATION_STATUS_ERROR",
    "GENERATION_STATUS_GENERATED",
    "GeneratedPuzzle",
    "PuzzleGenerationResult",
    "generate_puzzle",
]
