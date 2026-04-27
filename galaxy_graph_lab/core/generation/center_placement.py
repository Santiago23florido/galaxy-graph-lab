from __future__ import annotations

from dataclasses import dataclass
from random import Random
from types import MappingProxyType

from ..board import BoardSpec, Cell
from ..centers import CenterSpec
from .profiles import (
    CENTER_TYPE_CELL,
    CENTER_TYPE_EDGE,
    CENTER_TYPE_VERTEX,
    DifficultyProfile,
)


_TARGET_AREA_PER_CENTER = {
    "easy": 16,
    "medium": 11,
    "hard": 8,
}
_TARGET_COUNT_VARIATION = {
    "easy": 1,
    "medium": 1,
    "hard": 2,
}
_MIN_REGION_AREA = {
    "easy": 4,
    "medium": 3,
    "hard": 2,
}
_MAX_ASPECT_RATIO = {
    "easy": 4.0,
    "medium": 5.5,
    "hard": 7.0,
}


@dataclass(frozen=True, slots=True, order=True)
class RectangleRegion:
    """One axis-aligned rectangular region used as a constructive galaxy target."""

    top: int
    bottom: int
    left: int
    right: int

    @property
    def height(self) -> int:
        return self.bottom - self.top + 1

    @property
    def width(self) -> int:
        return self.right - self.left + 1

    @property
    def area(self) -> int:
        return self.height * self.width

    @property
    def center_type(self) -> str:
        if self.height % 2 == 1 and self.width % 2 == 1:
            return CENTER_TYPE_CELL
        if self.height % 2 == 0 and self.width % 2 == 0:
            return CENTER_TYPE_VERTEX
        return CENTER_TYPE_EDGE

    def cells(self) -> tuple[Cell, ...]:
        return tuple(
            Cell(row=row, col=col)
            for row in range(self.top, self.bottom + 1)
            for col in range(self.left, self.right + 1)
        )

    def center_spec(self, center_id: str) -> CenterSpec:
        return CenterSpec(
            id=center_id,
            row_coord2=self.top + self.bottom,
            col_coord2=self.left + self.right,
        )


@dataclass(frozen=True, slots=True)
class PlacedCenterRegion:
    """One placed center together with its constructive rectangular target region."""

    id: str
    rectangle: RectangleRegion
    center: CenterSpec
    center_type: str

    def cells(self) -> tuple[Cell, ...]:
        return self.rectangle.cells()


@dataclass(frozen=True, slots=True)
class CenterPlacementResult:
    """Structured output of the center-placement stage."""

    regions: tuple[PlacedCenterRegion, ...]
    target_center_count: int

    @property
    def centers(self) -> tuple[CenterSpec, ...]:
        return tuple(region.center for region in self.regions)

    @property
    def center_type_by_center(self):
        return MappingProxyType(
            {
                region.id: region.center_type
                for region in self.regions
            }
        )


@dataclass(frozen=True, slots=True)
class _SplitCandidate:
    region_index: int
    children: tuple[RectangleRegion, RectangleRegion]
    score: float


def _profile_min_region_area(profile: DifficultyProfile) -> int:
    return _MIN_REGION_AREA[profile.difficulty]


def _profile_max_aspect_ratio(profile: DifficultyProfile) -> float:
    return _MAX_ASPECT_RATIO[profile.difficulty]


def sample_target_center_count(
    board: BoardSpec,
    profile: DifficultyProfile,
    rng: Random,
) -> int:
    """Sample one target center count from the active difficulty profile."""

    area = board.rows * board.cols
    density_target = max(1, round(area / _TARGET_AREA_PER_CENTER[profile.difficulty]))
    feasible_max = max(1, area // _profile_min_region_area(profile))
    bounded_max = min(profile.max_center_count, feasible_max)
    base_target = min(max(profile.min_center_count, density_target), bounded_max)
    variation = _TARGET_COUNT_VARIATION[profile.difficulty]
    lower_bound = max(profile.min_center_count, base_target - variation)
    upper_bound = min(bounded_max, base_target + variation)
    return rng.randint(lower_bound, upper_bound)


def _rectangle_is_allowed(
    rectangle: RectangleRegion,
    profile: DifficultyProfile,
) -> bool:
    if rectangle.area < _profile_min_region_area(profile):
        return False

    aspect_ratio = max(
        rectangle.height / rectangle.width,
        rectangle.width / rectangle.height,
    )
    return aspect_ratio <= _profile_max_aspect_ratio(profile)


def _split_rectangles_horizontally(
    rectangle: RectangleRegion,
) -> tuple[tuple[RectangleRegion, RectangleRegion], ...]:
    return tuple(
        (
            RectangleRegion(
                top=rectangle.top,
                bottom=split_row,
                left=rectangle.left,
                right=rectangle.right,
            ),
            RectangleRegion(
                top=split_row + 1,
                bottom=rectangle.bottom,
                left=rectangle.left,
                right=rectangle.right,
            ),
        )
        for split_row in range(rectangle.top, rectangle.bottom)
    )


def _split_rectangles_vertically(
    rectangle: RectangleRegion,
) -> tuple[tuple[RectangleRegion, RectangleRegion], ...]:
    return tuple(
        (
            RectangleRegion(
                top=rectangle.top,
                bottom=rectangle.bottom,
                left=rectangle.left,
                right=split_col,
            ),
            RectangleRegion(
                top=rectangle.top,
                bottom=rectangle.bottom,
                left=split_col + 1,
                right=rectangle.right,
            ),
        )
        for split_col in range(rectangle.left, rectangle.right)
    )


def _mix_distance(
    rectangles: tuple[RectangleRegion, ...],
    profile: DifficultyProfile,
) -> float:
    total = len(rectangles)
    counts = {
        CENTER_TYPE_CELL: 0,
        CENTER_TYPE_EDGE: 0,
        CENTER_TYPE_VERTEX: 0,
    }
    for rectangle in rectangles:
        counts[rectangle.center_type] += 1

    return (
        abs((counts[CENTER_TYPE_CELL] / total) - profile.center_type_mix.cell_weight)
        + abs((counts[CENTER_TYPE_EDGE] / total) - profile.center_type_mix.edge_weight)
        + abs((counts[CENTER_TYPE_VERTEX] / total) - profile.center_type_mix.vertex_weight)
    )


def _shape_penalty(rectangles: tuple[RectangleRegion, ...]) -> float:
    return sum(
        max(rectangle.height / rectangle.width, rectangle.width / rectangle.height)
        for rectangle in rectangles
    ) / len(rectangles)


def _spacing_penalty(rectangles: tuple[RectangleRegion, ...]) -> float:
    penalty = 0.0
    centers = [
        ((rectangle.top + rectangle.bottom) / 2.0, (rectangle.left + rectangle.right) / 2.0)
        for rectangle in rectangles
    ]
    for index, (row_a, col_a) in enumerate(centers):
        for row_b, col_b in centers[index + 1 :]:
            manhattan_distance = abs(row_a - row_b) + abs(col_a - col_b)
            if manhattan_distance < 2.0:
                penalty += 2.0 - manhattan_distance
    return penalty


def _candidate_score(
    rectangles: tuple[RectangleRegion, ...],
    profile: DifficultyProfile,
) -> float:
    return (
        (_mix_distance(rectangles, profile) * 9.0)
        + _shape_penalty(rectangles)
        + _spacing_penalty(rectangles)
    )


def _enumerate_split_candidates(
    rectangles: tuple[RectangleRegion, ...],
    profile: DifficultyProfile,
) -> tuple[_SplitCandidate, ...]:
    candidates: list[_SplitCandidate] = []

    for region_index, rectangle in enumerate(rectangles):
        for children in (
            *_split_rectangles_horizontally(rectangle),
            *_split_rectangles_vertically(rectangle),
        ):
            if any(not _rectangle_is_allowed(child, profile) for child in children):
                continue

            next_rectangles = list(rectangles)
            next_rectangles.pop(region_index)
            next_rectangles.extend(children)
            score = _candidate_score(tuple(next_rectangles), profile)
            candidates.append(
                _SplitCandidate(
                    region_index=region_index,
                    children=children,
                    score=score,
                )
            )

    return tuple(candidates)


def _choose_split_candidate(
    rectangles: tuple[RectangleRegion, ...],
    profile: DifficultyProfile,
    rng: Random,
) -> _SplitCandidate | None:
    candidates = sorted(
        _enumerate_split_candidates(rectangles, profile),
        key=lambda candidate: (candidate.score, candidate.region_index),
    )
    if not candidates:
        return None

    top_window = candidates[: min(4, len(candidates))]
    return rng.choice(top_window)


def _apply_split_candidate(
    rectangles: tuple[RectangleRegion, ...],
    candidate: _SplitCandidate,
) -> tuple[RectangleRegion, ...]:
    next_rectangles = list(rectangles)
    next_rectangles.pop(candidate.region_index)
    next_rectangles.extend(candidate.children)
    return tuple(sorted(next_rectangles))


def _finalize_center_layout(
    rectangles: tuple[RectangleRegion, ...],
    target_center_count: int,
) -> CenterPlacementResult:
    placed_regions: list[PlacedCenterRegion] = []

    for index, rectangle in enumerate(sorted(rectangles)):
        center_id = f"g{index}"
        center = rectangle.center_spec(center_id)
        placed_regions.append(
            PlacedCenterRegion(
                id=center_id,
                rectangle=rectangle,
                center=center,
                center_type=rectangle.center_type,
            )
        )

    return CenterPlacementResult(
        regions=tuple(placed_regions),
        target_center_count=target_center_count,
    )


def place_candidate_centers(
    board: BoardSpec,
    profile: DifficultyProfile,
    rng: Random,
) -> CenterPlacementResult | None:
    """Place candidate centers by partitioning the board into symmetric rectangles."""

    target_center_count = sample_target_center_count(board, profile, rng)
    rectangles = (
        RectangleRegion(
            top=0,
            bottom=board.rows - 1,
            left=0,
            right=board.cols - 1,
        ),
    )

    while len(rectangles) < target_center_count:
        candidate = _choose_split_candidate(rectangles, profile, rng)
        if candidate is None:
            return None
        rectangles = _apply_split_candidate(rectangles, candidate)

    return _finalize_center_layout(rectangles, target_center_count)


__all__ = [
    "CenterPlacementResult",
    "PlacedCenterRegion",
    "RectangleRegion",
    "place_candidate_centers",
    "sample_target_center_count",
]
