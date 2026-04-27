from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from ..board import BoardSpec
from .request import (
    GENERATION_DIFFICULTIES,
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_HARD,
    GENERATION_DIFFICULTY_MEDIUM,
)


CENTER_TYPE_CELL = "cell"
CENTER_TYPE_EDGE = "edge"
CENTER_TYPE_VERTEX = "vertex"
CENTER_TYPES = (
    CENTER_TYPE_CELL,
    CENTER_TYPE_EDGE,
    CENTER_TYPE_VERTEX,
)


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_plain_float(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class CenterTypeMix:
    """Relative weight of cell, edge, and vertex centers for one profile."""

    cell_weight: float
    edge_weight: float
    vertex_weight: float

    def __post_init__(self) -> None:
        weights = (
            self.cell_weight,
            self.edge_weight,
            self.vertex_weight,
        )
        if any(not _is_plain_float(weight) for weight in weights):
            raise TypeError("Center-type weights must be numeric.")
        if any(float(weight) < 0.0 for weight in weights):
            raise ValueError("Center-type weights must be non-negative.")
        if abs(sum(float(weight) for weight in weights) - 1.0) > 1e-9:
            raise ValueError("Center-type weights must sum to 1.0.")


@dataclass(frozen=True, slots=True)
class OverlapTargetRange:
    """Target range for admissible-domain overlap under one profile."""

    min_ratio: float
    max_ratio: float

    def __post_init__(self) -> None:
        if not _is_plain_float(self.min_ratio) or not _is_plain_float(self.max_ratio):
            raise TypeError("Overlap target ratios must be numeric.")
        if not 0.0 <= float(self.min_ratio) <= float(self.max_ratio) <= 1.0:
            raise ValueError("Overlap target ratios must satisfy 0 <= min <= max <= 1.")


@dataclass(frozen=True, slots=True)
class DifficultyProfile:
    """Generation constraints attached to one named difficulty preset."""

    difficulty: str
    allowed_grid_sizes: tuple[BoardSpec, ...]
    min_center_count: int
    max_center_count: int
    center_type_mix: CenterTypeMix
    overlap_target_range: OverlapTargetRange
    uniqueness_required: bool

    def __post_init__(self) -> None:
        if self.difficulty not in GENERATION_DIFFICULTIES:
            raise ValueError(
                "difficulty must be one of: "
                f"{', '.join(GENERATION_DIFFICULTIES)}."
            )
        if not self.allowed_grid_sizes:
            raise ValueError("allowed_grid_sizes must be non-empty.")
        if any(not isinstance(grid_size, BoardSpec) for grid_size in self.allowed_grid_sizes):
            raise TypeError("allowed_grid_sizes must only contain BoardSpec instances.")
        if not _is_plain_int(self.min_center_count) or not _is_plain_int(self.max_center_count):
            raise TypeError("Center-count bounds must be integers.")
        if self.min_center_count <= 0:
            raise ValueError("min_center_count must be positive.")
        if self.min_center_count > self.max_center_count:
            raise ValueError("min_center_count must not exceed max_center_count.")


_GENERATION_DIFFICULTY_PROFILES = MappingProxyType(
    {
        GENERATION_DIFFICULTY_EASY: DifficultyProfile(
            difficulty=GENERATION_DIFFICULTY_EASY,
            allowed_grid_sizes=(
                BoardSpec(rows=5, cols=5),
                BoardSpec(rows=7, cols=7),
            ),
            min_center_count=1,
            max_center_count=4,
            center_type_mix=CenterTypeMix(
                cell_weight=0.7,
                edge_weight=0.25,
                vertex_weight=0.05,
            ),
            overlap_target_range=OverlapTargetRange(0.10, 0.25),
            uniqueness_required=True,
        ),
        GENERATION_DIFFICULTY_MEDIUM: DifficultyProfile(
            difficulty=GENERATION_DIFFICULTY_MEDIUM,
            allowed_grid_sizes=(
                BoardSpec(rows=5, cols=5),
                BoardSpec(rows=7, cols=7),
                BoardSpec(rows=9, cols=9),
            ),
            min_center_count=1,
            max_center_count=6,
            center_type_mix=CenterTypeMix(
                cell_weight=0.45,
                edge_weight=0.4,
                vertex_weight=0.15,
            ),
            overlap_target_range=OverlapTargetRange(0.20, 0.45),
            uniqueness_required=True,
        ),
        GENERATION_DIFFICULTY_HARD: DifficultyProfile(
            difficulty=GENERATION_DIFFICULTY_HARD,
            allowed_grid_sizes=(
                BoardSpec(rows=7, cols=7),
                BoardSpec(rows=9, cols=9),
            ),
            min_center_count=1,
            max_center_count=8,
            center_type_mix=CenterTypeMix(
                cell_weight=0.25,
                edge_weight=0.45,
                vertex_weight=0.30,
            ),
            overlap_target_range=OverlapTargetRange(0.35, 0.65),
            uniqueness_required=True,
        ),
    }
)


def difficulty_profile_for(difficulty: str) -> DifficultyProfile:
    """Return the canonical generation profile for one difficulty preset."""

    if difficulty not in _GENERATION_DIFFICULTY_PROFILES:
        raise ValueError(
            "difficulty must be one of: "
            f"{', '.join(GENERATION_DIFFICULTIES)}."
        )
    return _GENERATION_DIFFICULTY_PROFILES[difficulty]


def difficulty_profiles() -> tuple[DifficultyProfile, ...]:
    """Return the generation profiles in stable difficulty order."""

    return tuple(
        _GENERATION_DIFFICULTY_PROFILES[difficulty]
        for difficulty in GENERATION_DIFFICULTIES
    )


__all__ = [
    "CENTER_TYPE_CELL",
    "CENTER_TYPE_EDGE",
    "CENTER_TYPE_VERTEX",
    "CENTER_TYPES",
    "CenterTypeMix",
    "DifficultyProfile",
    "OverlapTargetRange",
    "difficulty_profile_for",
    "difficulty_profiles",
]
