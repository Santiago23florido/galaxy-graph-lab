from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from random import Random
from types import MappingProxyType

from ..board import Cell
from ..geometry import twin_cell
from ..model_data import PuzzleData
from .center_placement import CenterPlacementResult, PlacedCenterRegion
from .difficulty import region_irregularity
from .profiles import DifficultyProfile


def _freeze_assignment_by_cell(data: Mapping[Cell, str]) -> Mapping[Cell, str]:
    return MappingProxyType(dict(data))


def _initial_ownership_by_cell(
    constructive_assignment: Mapping[str, tuple[Cell, ...]],
) -> dict[Cell, str]:
    ownership: dict[Cell, str] = {}
    for center_id, cells in constructive_assignment.items():
        for cell in cells:
            ownership[cell] = center_id
    return ownership


def _initial_cells_by_center(
    constructive_assignment: Mapping[str, tuple[Cell, ...]],
) -> dict[str, set[Cell]]:
    return {
        center_id: set(cells)
        for center_id, cells in constructive_assignment.items()
    }


def _protected_kernel_owners_by_cell(
    puzzle_data: PuzzleData,
) -> dict[Cell, frozenset[str]]:
    protected_owners: dict[Cell, set[str]] = {}
    for center in puzzle_data.centers:
        for cell in puzzle_data.kernel_by_center[center.id]:
            protected_owners.setdefault(cell, set()).add(center.id)
    return {
        cell: frozenset(center_ids)
        for cell, center_ids in protected_owners.items()
    }


def _orbit_for_cell(
    puzzle_data: PuzzleData,
    center_id: str,
    cell: Cell,
) -> tuple[Cell, ...] | None:
    center = puzzle_data.center_by_id[center_id]
    twin = twin_cell(puzzle_data.board, center, cell)
    if twin is None:
        return None
    return tuple(sorted({cell, twin}))


def _orbit_touches_region(
    puzzle_data: PuzzleData,
    region_cells: set[Cell],
    orbit: tuple[Cell, ...],
) -> bool:
    for orbit_cell in orbit:
        if any(neighbor in region_cells for neighbor in puzzle_data.neighbors[orbit_cell]):
            return True
    return False


def _orbit_is_transfer_safe(
    orbit: tuple[Cell, ...],
    candidate_center_id: str,
    protected_kernel_owners_by_cell: Mapping[Cell, frozenset[str]],
) -> bool:
    for cell in orbit:
        protected_owners = protected_kernel_owners_by_cell.get(cell, frozenset())
        if protected_owners and candidate_center_id not in protected_owners:
            return False
    return True


def _region_center_point(region: PlacedCenterRegion) -> tuple[float, float]:
    rectangle = region.rectangle
    return (
        (rectangle.top + rectangle.bottom) / 2.0,
        (rectangle.left + rectangle.right) / 2.0,
    )


def _orbit_score(
    puzzle_data: PuzzleData,
    region: PlacedCenterRegion,
    region_cells: set[Cell],
    orbit: tuple[Cell, ...],
    target_irregularity: float,
) -> float:
    base_cells = set(region.cells())
    next_cells = region_cells.union(orbit)
    next_irregularity = region_irregularity(next_cells)
    current_rows = [cell.row for cell in region_cells]
    current_cols = [cell.col for cell in region_cells]
    next_rows = [cell.row for cell in next_cells]
    next_cols = [cell.col for cell in next_cells]
    current_bounding_box_area = (
        (max(current_rows) - min(current_rows) + 1)
        * (max(current_cols) - min(current_cols) + 1)
    )
    next_bounding_box_area = (
        (max(next_rows) - min(next_rows) + 1)
        * (max(next_cols) - min(next_cols) + 1)
    )
    center_row, center_col = _region_center_point(region)
    distance_penalty = (
        sum(
            abs(cell.row - center_row) + abs(cell.col - center_col)
            for cell in orbit
        )
        / len(orbit)
    )
    outside_gain = sum(1 for cell in orbit if cell not in base_cells)
    adjacency_bonus = sum(
        1
        for cell in orbit
        if any(neighbor in region_cells for neighbor in puzzle_data.neighbors[cell])
    )
    bounding_box_growth_penalty = max(
        0,
        next_bounding_box_area - current_bounding_box_area - len(orbit),
    )

    return (
        abs(target_irregularity - next_irregularity) * 4.0
        + (bounding_box_growth_penalty * 0.9)
        + (distance_penalty * 0.12)
        - (outside_gain * 0.8)
        - (adjacency_bonus * 0.35)
    )


def _choose_candidate_orbit(
    puzzle_data: PuzzleData,
    region: PlacedCenterRegion,
    region_cells: set[Cell],
    ownership_by_cell: Mapping[Cell, str],
    protected_kernel_owners_by_cell: Mapping[Cell, frozenset[str]],
    target_irregularity: float,
    rng: Random,
) -> tuple[Cell, ...] | None:
    seen_orbits: set[tuple[Cell, ...]] = set()
    candidates: list[tuple[float, tuple[Cell, ...]]] = []

    for cell in puzzle_data.admissible_cells_by_center[region.id]:
        orbit = _orbit_for_cell(puzzle_data, region.id, cell)
        if orbit is None or orbit in seen_orbits:
            continue
        seen_orbits.add(orbit)

        if all(ownership_by_cell[orbit_cell] == region.id for orbit_cell in orbit):
            continue
        if not _orbit_is_transfer_safe(
            orbit,
            region.id,
            protected_kernel_owners_by_cell,
        ):
            continue
        if not _orbit_touches_region(puzzle_data, region_cells, orbit):
            continue

        next_cells = region_cells.union(orbit)
        if not puzzle_data.graph.is_connected(next_cells):
            continue

        candidates.append(
            (
                _orbit_score(
                    puzzle_data,
                    region,
                    region_cells,
                    orbit,
                    target_irregularity,
                ),
                orbit,
            )
        )

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]))
    return rng.choice([orbit for _, orbit in candidates[: min(4, len(candidates))]])


def _apply_orbit_claim(
    orbit: tuple[Cell, ...],
    center_id: str,
    ownership_by_cell: dict[Cell, str],
    cells_by_center: dict[str, set[Cell]],
) -> None:
    for cell in orbit:
        previous_owner = ownership_by_cell[cell]
        if previous_owner == center_id:
            continue
        cells_by_center[previous_owner].remove(cell)
        ownership_by_cell[cell] = center_id
        cells_by_center[center_id].add(cell)


def _selected_regions_for_shaping(
    placement: CenterPlacementResult,
    profile: DifficultyProfile,
) -> tuple[PlacedCenterRegion, ...]:
    if profile.min_non_rectangular_regions == 0:
        return ()

    extra_regions = 1
    if profile.difficulty == "hard" and len(placement.regions) > profile.min_non_rectangular_regions:
        extra_regions = 2

    target_count = min(
        len(placement.regions),
        profile.min_non_rectangular_regions + extra_regions,
    )
    ordered_regions = sorted(
        placement.regions,
        key=lambda region: (-region.rectangle.area, region.id),
    )
    return tuple(ordered_regions[:target_count])


@dataclass(frozen=True, slots=True)
class SolverShapeGuidance:
    """Sparse ownership hints used to steer the exact solver away from rectangles."""

    preferred_assignment_by_cell: Mapping[Cell, str]
    avoid_assignment_by_cell: Mapping[Cell, str]


def build_preferred_assignment_by_cell(
    puzzle_data: PuzzleData,
    placement: CenterPlacementResult,
    constructive_assignment: Mapping[str, tuple[Cell, ...]],
    profile: DifficultyProfile,
    rng: Random,
    *,
    aggressiveness: float = 1.0,
) -> SolverShapeGuidance:
    """Build sparse solver guidance that nudges medium and hard away from rectangles."""

    ownership_by_cell = _initial_ownership_by_cell(constructive_assignment)
    if profile.min_non_rectangular_regions == 0:
        return SolverShapeGuidance(
            preferred_assignment_by_cell=MappingProxyType({}),
            avoid_assignment_by_cell=MappingProxyType({}),
        )

    cells_by_center = _initial_cells_by_center(constructive_assignment)
    protected_kernel_owners_by_cell = _protected_kernel_owners_by_cell(puzzle_data)
    target_irregularity = (
        profile.irregularity_target_range.min_ratio
        + profile.irregularity_target_range.max_ratio
    ) / 2.0
    target_irregularity = min(
        0.95,
        target_irregularity * max(0.5, aggressiveness),
    )

    selected_regions = _selected_regions_for_shaping(placement, profile)
    for region in selected_regions:
        max_claims = max(
            4,
            round(region.rectangle.area * (target_irregularity + 0.28) * aggressiveness),
        )
        min_claims = 2
        if profile.difficulty == "hard":
            min_claims = 3
        if aggressiveness > 1.2:
            min_claims += 1

        claim_count = 0
        for _ in range(max_claims):
            current_cells = cells_by_center[region.id]
            if (
                claim_count >= min_claims
                and region_irregularity(current_cells) >= target_irregularity
            ):
                break

            orbit = _choose_candidate_orbit(
                puzzle_data,
                region,
                current_cells,
                ownership_by_cell,
                protected_kernel_owners_by_cell,
                target_irregularity,
                rng,
            )
            if orbit is None:
                break

            _apply_orbit_claim(
                orbit,
                region.id,
                ownership_by_cell,
                cells_by_center,
            )
            claim_count += 1

    base_ownership_by_cell = _initial_ownership_by_cell(constructive_assignment)
    preferred_assignment_by_cell = {
        cell: center_id
        for cell, center_id in ownership_by_cell.items()
        if base_ownership_by_cell[cell] != center_id
    }
    avoid_assignment_by_cell = {
        cell: base_ownership_by_cell[cell]
        for region in selected_regions
        for cell in region.cells()
    }

    return SolverShapeGuidance(
        preferred_assignment_by_cell=_freeze_assignment_by_cell(
            preferred_assignment_by_cell
        ),
        avoid_assignment_by_cell=_freeze_assignment_by_cell(
            avoid_assignment_by_cell
        ),
    )


__all__ = ["SolverShapeGuidance", "build_preferred_assignment_by_cell"]
