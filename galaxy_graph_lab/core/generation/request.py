from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..board import BoardSpec

if TYPE_CHECKING:
    from .profiles import DifficultyProfile


GENERATION_DIFFICULTY_EASY = "easy"
GENERATION_DIFFICULTY_MEDIUM = "medium"
GENERATION_DIFFICULTY_HARD = "hard"
GENERATION_DIFFICULTIES = (
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_MEDIUM,
    GENERATION_DIFFICULTY_HARD,
)


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class PuzzleGenerationRequest:
    """Immutable request for building one puzzle instance."""

    difficulty: str
    grid_size: BoardSpec
    random_seed: int | None = None
    max_generation_retries: int = 1

    def __post_init__(self) -> None:
        if self.difficulty not in GENERATION_DIFFICULTIES:
            raise ValueError(
                "difficulty must be one of: "
                f"{', '.join(GENERATION_DIFFICULTIES)}."
            )
        if not isinstance(self.grid_size, BoardSpec):
            raise TypeError("grid_size must be a BoardSpec.")
        if self.random_seed is not None and not _is_plain_int(self.random_seed):
            raise TypeError("random_seed must be an integer or None.")
        if not _is_plain_int(self.max_generation_retries):
            raise TypeError("max_generation_retries must be an integer.")
        if self.max_generation_retries <= 0:
            raise ValueError("max_generation_retries must be positive.")
        if self.grid_size not in self.difficulty_profile.allowed_grid_sizes:
            raise ValueError(
                "grid_size is not allowed for the selected difficulty: "
                f"{self.difficulty}."
            )

    @property
    def difficulty_profile(self) -> "DifficultyProfile":
        from .profiles import difficulty_profile_for

        return difficulty_profile_for(self.difficulty)


__all__ = [
    "GENERATION_DIFFICULTIES",
    "GENERATION_DIFFICULTY_EASY",
    "GENERATION_DIFFICULTY_HARD",
    "GENERATION_DIFFICULTY_MEDIUM",
    "PuzzleGenerationRequest",
]
