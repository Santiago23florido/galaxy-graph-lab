from __future__ import annotations

from dataclasses import dataclass

from ..centers import CenterSpec
from ..model_data import PuzzleData
from .profiles import DifficultyProfile
from .request import PuzzleGenerationRequest


GENERATION_STATUS_GENERATED = "generated"
GENERATION_STATUS_ERROR = "generation_error"


@dataclass(frozen=True, slots=True)
class GeneratedPuzzle:
    """Structured puzzle payload returned by the generation pipeline."""

    name: str
    puzzle_data: PuzzleData


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


def _build_placeholder_puzzle(
    request: PuzzleGenerationRequest,
    profile: DifficultyProfile,
) -> GeneratedPuzzle:
    # Phase 1 keeps one deterministic, geometry-safe placeholder so the rest
    # of the app can already depend on the generation API.
    # Phase 2 resolves the profile here so later generation logic can vary by
    # difficulty without branching outside the generation module.
    center = CenterSpec(
        id="g0",
        row_coord2=request.grid_size.rows - 1,
        col_coord2=request.grid_size.cols - 1,
    )
    puzzle_data = PuzzleData.from_specs(request.grid_size, (center,))
    puzzle_name = (
        f"{request.difficulty.title()} "
        f"{request.grid_size.rows}x{request.grid_size.cols}"
    )
    return GeneratedPuzzle(name=puzzle_name, puzzle_data=puzzle_data)


def generate_puzzle(request: PuzzleGenerationRequest) -> PuzzleGenerationResult:
    """Build one puzzle instance through the public generation entrypoint."""

    try:
        profile = request.difficulty_profile
        puzzle = _build_placeholder_puzzle(request, profile)
    except Exception as exc:
        return PuzzleGenerationResult(
            success=False,
            status_code=-1,
            status_label=GENERATION_STATUS_ERROR,
            message=f"The generator could not build a puzzle: {exc}.",
            request=request,
            profile=None,
            puzzle=None,
            retry_count=0,
            random_seed_used=request.random_seed,
        )

    return PuzzleGenerationResult(
        success=True,
        status_code=0,
        status_label=GENERATION_STATUS_GENERATED,
        message="Puzzle generated successfully.",
        request=request,
        profile=profile,
        puzzle=puzzle,
        retry_count=0,
        random_seed_used=request.random_seed,
    )


__all__ = [
    "GENERATION_STATUS_ERROR",
    "GENERATION_STATUS_GENERATED",
    "GeneratedPuzzle",
    "PuzzleGenerationResult",
    "generate_puzzle",
]
