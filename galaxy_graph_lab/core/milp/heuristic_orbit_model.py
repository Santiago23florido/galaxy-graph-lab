from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random
from time import perf_counter
from types import MappingProxyType

from ..board import Cell
from ..model_data import PuzzleData
from ..validators import validate_assignment
from .base_model import GalaxyAssignment


def _freeze_assignment_by_cell(data: Mapping[Cell, str]) -> Mapping[Cell, str]:
    return MappingProxyType(dict(data))


def _freeze_cells_by_center(
    data: Mapping[str, Sequence[Cell]],
) -> Mapping[str, tuple[Cell, ...]]:
    return MappingProxyType(
        {
            center_id: tuple(sorted(cells))
            for center_id, cells in data.items()
        }
    )


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _stable_seed(puzzle_data: PuzzleData) -> int:
    seed = (puzzle_data.board.rows * 1009) + (puzzle_data.board.cols * 9176)
    for center in puzzle_data.centers:
        seed = (
            (seed * 1315423911)
            ^ (center.row_coord2 * 97531)
            ^ (center.col_coord2 * 19213)
            ^ sum(ord(character) for character in center.id)
        ) & 0x7FFFFFFF
    return seed


def _region_boundary_size(
    puzzle_data: PuzzleData,
    cells: set[Cell],
) -> int:
    if not cells:
        return 0
    boundary_size = 0
    for cell in cells:
        boundary_size += sum(
            1 for neighbor in puzzle_data.neighbors[cell] if neighbor not in cells
        )
    return boundary_size


def _orbit_touches_region(
    puzzle_data: PuzzleData,
    region_cells: set[Cell],
    orbit: Sequence[Cell],
) -> bool:
    return any(
        orbit_cell in region_cells
        or any(neighbor in region_cells for neighbor in puzzle_data.neighbors[orbit_cell])
        for orbit_cell in orbit
    )


def _build_assignment_from_cells_by_center(
    puzzle_data: PuzzleData,
    cells_by_center: Mapping[str, set[Cell]],
) -> GalaxyAssignment:
    assigned_center_by_cell: dict[Cell, str] = {}
    for center in puzzle_data.centers:
        for cell in sorted(cells_by_center[center.id]):
            assigned_center_by_cell[cell] = center.id
    return GalaxyAssignment(
        assigned_center_by_cell=_freeze_assignment_by_cell(assigned_center_by_cell),
        cells_by_center=_freeze_cells_by_center(cells_by_center),
    )


@dataclass(frozen=True, slots=True)
class HeuristicOrbitSolveResult:
    """Structured result of solving through the heuristic orbit backend."""

    success: bool
    status: int
    message: str
    objective_value: float | None
    mip_gap: float | None
    mip_node_count: int | None
    assignment: GalaxyAssignment | None
    attempt_count: int


@dataclass(frozen=True, slots=True)
class _OrbitCandidate:
    center_id: str
    orbit: tuple[Cell, ...]
    score: float


@dataclass(frozen=True, slots=True)
class HeuristicOrbitModel:
    """Symmetry-orbit constructive search model for Spiral Galaxies."""

    puzzle_data: PuzzleData
    orbit_by_center_and_cell: Mapping[str, Mapping[Cell, tuple[Cell, ...]]]
    unique_orbits_by_center: Mapping[str, tuple[tuple[Cell, ...], ...]]
    candidate_centers_by_cell: Mapping[Cell, tuple[str, ...]]
    target_area_by_center: Mapping[str, float]
    center_point_by_id: Mapping[str, tuple[float, float]]
    kernel_cells_by_center: Mapping[str, frozenset[Cell]]

    @classmethod
    def from_puzzle_data(cls, puzzle_data: PuzzleData) -> "HeuristicOrbitModel":
        orbit_by_center_and_cell: dict[str, Mapping[Cell, tuple[Cell, ...]]] = {}
        unique_orbits_by_center: dict[str, tuple[tuple[Cell, ...], ...]] = {}
        candidate_centers_by_cell: dict[Cell, list[str]] = {
            cell: []
            for cell in puzzle_data.cells
        }
        target_area_by_center: dict[str, float] = {}
        center_point_by_id: dict[str, tuple[float, float]] = {}
        kernel_cells_by_center: dict[str, frozenset[Cell]] = {}
        coverage_count = {
            cell: 0
            for cell in puzzle_data.cells
        }

        for center in puzzle_data.centers:
            center_point_by_id[center.id] = (
                float(center.row_coord),
                float(center.col_coord),
            )
            kernel_cells_by_center[center.id] = frozenset(
                puzzle_data.kernel_by_center[center.id]
            )
            for cell in puzzle_data.admissible_cells_by_center[center.id]:
                coverage_count[cell] += 1
                candidate_centers_by_cell[cell].append(center.id)

        for center in puzzle_data.centers:
            orbit_lookup: dict[Cell, tuple[Cell, ...]] = {}
            seen_orbits: set[tuple[Cell, ...]] = set()
            unique_orbits: list[tuple[Cell, ...]] = []
            target_area = 0.0
            for cell in puzzle_data.admissible_cells_by_center[center.id]:
                twin = puzzle_data.twin_by_center_and_cell[center.id][cell]
                orbit = tuple(sorted({cell, twin}))
                orbit_lookup[cell] = orbit
                if orbit not in seen_orbits:
                    seen_orbits.add(orbit)
                    unique_orbits.append(orbit)
                target_area += 1.0 / max(1, coverage_count[cell])

            orbit_by_center_and_cell[center.id] = MappingProxyType(dict(orbit_lookup))
            unique_orbits_by_center[center.id] = tuple(unique_orbits)
            target_area_by_center[center.id] = max(
                float(len(kernel_cells_by_center[center.id])),
                target_area,
            )

        return cls(
            puzzle_data=puzzle_data,
            orbit_by_center_and_cell=MappingProxyType(dict(orbit_by_center_and_cell)),
            unique_orbits_by_center=MappingProxyType(dict(unique_orbits_by_center)),
            candidate_centers_by_cell=MappingProxyType(
                {
                    cell: tuple(center_ids)
                    for cell, center_ids in candidate_centers_by_cell.items()
                }
            ),
            target_area_by_center=MappingProxyType(dict(target_area_by_center)),
            center_point_by_id=MappingProxyType(dict(center_point_by_id)),
            kernel_cells_by_center=MappingProxyType(dict(kernel_cells_by_center)),
        )

    def _new_cells_in_orbit(
        self,
        owner_by_cell: Mapping[Cell, str],
        orbit: Sequence[Cell],
    ) -> tuple[Cell, ...]:
        return tuple(cell for cell in orbit if cell not in owner_by_cell)

    def _guidance_objective(
        self,
        owner_by_cell: Mapping[Cell, str],
        preferred_assignment_by_cell: Mapping[Cell, str],
        avoid_assignment_by_cell: Mapping[Cell, str],
    ) -> float:
        preferred_matches = sum(
            1
            for cell, center_id in preferred_assignment_by_cell.items()
            if owner_by_cell.get(cell) == center_id
        )
        avoid_matches = sum(
            1
            for cell, center_id in avoid_assignment_by_cell.items()
            if owner_by_cell.get(cell) == center_id
        )
        return float((-5.0 * preferred_matches) + (3.0 * avoid_matches))

    def _preferred_is_satisfied(
        self,
        owner_by_cell: Mapping[Cell, str],
        preferred_assignment_by_cell: Mapping[Cell, str],
    ) -> bool:
        return all(
            owner_by_cell.get(cell) == center_id
            for cell, center_id in preferred_assignment_by_cell.items()
        )

    def _mismatch_count_against_avoid(
        self,
        owner_by_cell: Mapping[Cell, str],
        avoid_assignment_by_cell: Mapping[Cell, str],
    ) -> int:
        return sum(
            1
            for cell, center_id in avoid_assignment_by_cell.items()
            if owner_by_cell.get(cell) != center_id
        )

    def _orbit_ambiguity(
        self,
        orbit: Sequence[Cell],
        preferred_assignment_by_cell: Mapping[Cell, str],
        *,
        require_preferred_assignment: bool,
    ) -> int:
        admissible_center_count = 0
        for center in self.puzzle_data.centers:
            center_id = center.id
            if any(
                cell not in self.orbit_by_center_and_cell[center_id]
                for cell in orbit
            ):
                continue
            if require_preferred_assignment and any(
                preferred_assignment_by_cell.get(cell) not in {None, center_id}
                for cell in orbit
            ):
                continue
            admissible_center_count += 1
        return max(1, admissible_center_count)

    def _candidate_score(
        self,
        *,
        center_id: str,
        orbit: Sequence[Cell],
        owner_by_cell: Mapping[Cell, str],
        cells_by_center: Mapping[str, set[Cell]],
        preferred_assignment_by_cell: Mapping[Cell, str],
        avoid_assignment_by_cell: Mapping[Cell, str],
        require_preferred_assignment: bool,
    ) -> float:
        region_cells = cells_by_center[center_id]
        new_cells = self._new_cells_in_orbit(owner_by_cell, orbit)
        if not new_cells:
            return float("inf")

        ambiguity_penalty = self._orbit_ambiguity(
            orbit,
            preferred_assignment_by_cell,
            require_preferred_assignment=require_preferred_assignment,
        ) * 2.8
        center_row, center_col = self.center_point_by_id[center_id]
        distance_penalty = (
            sum(
                abs(cell.row - center_row) + abs(cell.col - center_col)
                for cell in orbit
            )
            / len(orbit)
        ) * 0.16

        boundary_before = _region_boundary_size(self.puzzle_data, region_cells)
        next_cells = region_cells.union(new_cells)
        boundary_after = _region_boundary_size(self.puzzle_data, next_cells)
        boundary_growth_penalty = max(0, boundary_after - boundary_before) * 0.35

        target_area = self.target_area_by_center[center_id]
        size_penalty = abs(len(next_cells) - target_area) * 0.22

        adjacency_bonus = sum(
            1
            for cell in orbit
            if any(neighbor in region_cells for neighbor in self.puzzle_data.neighbors[cell])
        ) * 0.8

        preferred_bonus = sum(
            1
            for cell in orbit
            if preferred_assignment_by_cell.get(cell) == center_id
        ) * 8.0
        preferred_conflict_penalty = sum(
            1
            for cell in orbit
            if preferred_assignment_by_cell.get(cell) not in {None, center_id}
        ) * 20.0
        avoid_penalty = sum(
            1
            for cell in orbit
            if avoid_assignment_by_cell.get(cell) == center_id
        ) * 6.5

        if require_preferred_assignment and preferred_conflict_penalty > 0.0:
            return float("inf")

        return (
            ambiguity_penalty
            + distance_penalty
            + boundary_growth_penalty
            + size_penalty
            + avoid_penalty
            + preferred_conflict_penalty
            - adjacency_bonus
            - preferred_bonus
        )

    def _can_claim_orbit(
        self,
        center_id: str,
        orbit: Sequence[Cell],
        owner_by_cell: Mapping[Cell, str],
        cells_by_center: Mapping[str, set[Cell]],
        preferred_assignment_by_cell: Mapping[Cell, str],
        *,
        require_preferred_assignment: bool,
    ) -> bool:
        if require_preferred_assignment and any(
            preferred_assignment_by_cell.get(cell) not in {None, center_id}
            for cell in orbit
        ):
            return False

        if any(owner_by_cell.get(cell) not in {None, center_id} for cell in orbit):
            return False

        new_cells = self._new_cells_in_orbit(owner_by_cell, orbit)
        if not new_cells:
            return False

        region_cells = cells_by_center[center_id]
        if region_cells and not _orbit_touches_region(self.puzzle_data, region_cells, orbit):
            return False

        next_cells = region_cells.union(new_cells)
        return self.puzzle_data.graph.is_connected(next_cells)

    def _candidate_orbits(
        self,
        owner_by_cell: Mapping[Cell, str],
        cells_by_center: Mapping[str, set[Cell]],
        preferred_assignment_by_cell: Mapping[Cell, str],
        avoid_assignment_by_cell: Mapping[Cell, str],
        *,
        require_preferred_assignment: bool,
    ) -> list[_OrbitCandidate]:
        candidates: list[_OrbitCandidate] = []
        for center in self.puzzle_data.centers:
            center_id = center.id
            for orbit in self.unique_orbits_by_center[center_id]:
                if not self._can_claim_orbit(
                    center_id,
                    orbit,
                    owner_by_cell,
                    cells_by_center,
                    preferred_assignment_by_cell,
                    require_preferred_assignment=require_preferred_assignment,
                ):
                    continue
                candidates.append(
                    _OrbitCandidate(
                        center_id=center_id,
                        orbit=orbit,
                        score=self._candidate_score(
                            center_id=center_id,
                            orbit=orbit,
                            owner_by_cell=owner_by_cell,
                            cells_by_center=cells_by_center,
                            preferred_assignment_by_cell=preferred_assignment_by_cell,
                            avoid_assignment_by_cell=avoid_assignment_by_cell,
                            require_preferred_assignment=require_preferred_assignment,
                        ),
                    )
                )
        candidates.sort(key=lambda candidate: (candidate.score, candidate.center_id, candidate.orbit))
        return candidates

    def _apply_orbit(
        self,
        owner_by_cell: dict[Cell, str],
        cells_by_center: dict[str, set[Cell]],
        center_id: str,
        orbit: Sequence[Cell],
    ) -> None:
        for cell in orbit:
            if owner_by_cell.get(cell) == center_id:
                continue
            owner_by_cell[cell] = center_id
            cells_by_center[center_id].add(cell)

    def _initial_state(self) -> tuple[dict[Cell, str], dict[str, set[Cell]]]:
        owner_by_cell: dict[Cell, str] = {}
        cells_by_center: dict[str, set[Cell]] = {
            center.id: set()
            for center in self.puzzle_data.centers
        }
        for center in self.puzzle_data.centers:
            center_id = center.id
            for cell in self.kernel_cells_by_center[center_id]:
                existing_owner = owner_by_cell.get(cell)
                if existing_owner not in {None, center_id}:
                    raise ValueError(
                        "Kernel cells overlap between different centers; the heuristic "
                        "backend cannot build a consistent initial state."
                    )
                owner_by_cell[cell] = center_id
                cells_by_center[center_id].add(cell)
        return owner_by_cell, cells_by_center

    def _local_improvement(
        self,
        owner_by_cell: dict[Cell, str],
        cells_by_center: dict[str, set[Cell]],
        preferred_assignment_by_cell: Mapping[Cell, str],
        avoid_assignment_by_cell: Mapping[Cell, str],
        *,
        require_preferred_assignment: bool,
        minimum_mismatches_against_avoid: int | None,
        deadline: float,
    ) -> None:
        current_score = self._guidance_objective(
            owner_by_cell,
            preferred_assignment_by_cell,
            avoid_assignment_by_cell,
        )

        for _ in range(max(8, len(self.puzzle_data.cells) * 2)):
            if perf_counter() >= deadline:
                return

            target_cells = [
                cell
                for cell, center_id in preferred_assignment_by_cell.items()
                if owner_by_cell.get(cell) != center_id
            ]
            if not target_cells:
                target_cells = [
                    cell
                    for cell, center_id in avoid_assignment_by_cell.items()
                    if owner_by_cell.get(cell) == center_id
                ]
            if not target_cells:
                return

            best_move: tuple[str, tuple[Cell, ...], dict[Cell, str], dict[str, set[Cell]], float] | None = None
            for cell in target_cells:
                preferred_owner = preferred_assignment_by_cell.get(cell)
                candidate_centers = (
                    (preferred_owner,)
                    if preferred_owner is not None
                    else self.candidate_centers_by_cell[cell]
                )
                for center_id in candidate_centers:
                    orbit = self.orbit_by_center_and_cell[center_id].get(cell)
                    if orbit is None:
                        continue
                    next_owner_by_cell = dict(owner_by_cell)
                    next_cells_by_center = {
                        owner: set(cells)
                        for owner, cells in cells_by_center.items()
                    }
                    for orbit_cell in orbit:
                        previous_owner = next_owner_by_cell.get(orbit_cell)
                        if previous_owner == center_id:
                            continue
                        if previous_owner is not None:
                            next_cells_by_center[previous_owner].remove(orbit_cell)
                        next_owner_by_cell[orbit_cell] = center_id
                        next_cells_by_center[center_id].add(orbit_cell)

                    validation = validate_assignment(
                        self.puzzle_data,
                        next_cells_by_center,
                    )
                    if not validation.is_valid:
                        continue
                    if require_preferred_assignment and not self._preferred_is_satisfied(
                        next_owner_by_cell,
                        preferred_assignment_by_cell,
                    ):
                        continue
                    if (
                        minimum_mismatches_against_avoid is not None
                        and self._mismatch_count_against_avoid(
                            next_owner_by_cell,
                            avoid_assignment_by_cell,
                        )
                        < minimum_mismatches_against_avoid
                    ):
                        continue
                    next_score = self._guidance_objective(
                        next_owner_by_cell,
                        preferred_assignment_by_cell,
                        avoid_assignment_by_cell,
                    )
                    if next_score >= current_score - 1e-9:
                        continue
                    if best_move is None or next_score < best_move[4]:
                        best_move = (
                            center_id,
                            orbit,
                            next_owner_by_cell,
                            next_cells_by_center,
                            next_score,
                        )

            if best_move is None:
                return

            owner_by_cell.clear()
            owner_by_cell.update(best_move[2])
            cells_by_center.clear()
            cells_by_center.update(best_move[3])
            current_score = best_move[4]

    def _construct_assignment(
        self,
        rng: Random,
        preferred_assignment_by_cell: Mapping[Cell, str],
        avoid_assignment_by_cell: Mapping[Cell, str],
        *,
        require_preferred_assignment: bool,
        minimum_mismatches_against_avoid: int | None,
        deadline: float,
    ) -> GalaxyAssignment | None:
        owner_by_cell, cells_by_center = self._initial_state()
        all_cells = set(self.puzzle_data.cells)

        while len(owner_by_cell) < len(self.puzzle_data.cells):
            if perf_counter() >= deadline:
                return None

            candidates = self._candidate_orbits(
                owner_by_cell,
                cells_by_center,
                preferred_assignment_by_cell,
                avoid_assignment_by_cell,
                require_preferred_assignment=require_preferred_assignment,
            )
            if not candidates:
                return None

            sample_size = min(5, len(candidates))
            chosen_candidate = rng.choice(candidates[:sample_size])
            self._apply_orbit(
                owner_by_cell,
                cells_by_center,
                chosen_candidate.center_id,
                chosen_candidate.orbit,
            )

        if set(owner_by_cell) != all_cells:
            return None

        self._local_improvement(
            owner_by_cell,
            cells_by_center,
            preferred_assignment_by_cell,
            avoid_assignment_by_cell,
            require_preferred_assignment=require_preferred_assignment,
            minimum_mismatches_against_avoid=minimum_mismatches_against_avoid,
            deadline=deadline,
        )

        validation_result = validate_assignment(self.puzzle_data, cells_by_center)
        if not validation_result.is_valid:
            return None
        if require_preferred_assignment and not self._preferred_is_satisfied(
            owner_by_cell,
            preferred_assignment_by_cell,
        ):
            return None
        if (
            minimum_mismatches_against_avoid is not None
            and self._mismatch_count_against_avoid(
                owner_by_cell,
                avoid_assignment_by_cell,
            )
            < minimum_mismatches_against_avoid
        ):
            return None

        return _build_assignment_from_cells_by_center(self.puzzle_data, cells_by_center)

    def solve(
        self,
        *,
        time_limit: float,
        preferred_assignment_by_cell: Mapping[Cell, str] | None = None,
        avoid_assignment_by_cell: Mapping[Cell, str] | None = None,
        minimum_mismatches_against_avoid: int | None = None,
        require_preferred_assignment: bool = False,
        random_seed: int | None = None,
        max_starts: int | None = None,
    ) -> HeuristicOrbitSolveResult:
        """Run the orbit-based constructive heuristic until a valid assignment is found."""

        if time_limit <= 0.0:
            raise ValueError("time_limit must be positive for the heuristic backend.")
        if minimum_mismatches_against_avoid is not None and minimum_mismatches_against_avoid < 0:
            raise ValueError("minimum_mismatches_against_avoid must be non-negative.")

        preferred_assignment = dict(preferred_assignment_by_cell or {})
        avoid_assignment = dict(avoid_assignment_by_cell or {})
        deadline = perf_counter() + time_limit
        seed = _stable_seed(self.puzzle_data) if random_seed is None else random_seed
        attempt_count = 0
        hard_limit = max_starts if max_starts is not None else max(8, len(self.puzzle_data.cells) * 6)

        while perf_counter() < deadline and attempt_count < hard_limit:
            attempt_count += 1
            rng = Random(seed + (attempt_count * 10007))
            assignment = self._construct_assignment(
                rng,
                preferred_assignment,
                avoid_assignment,
                require_preferred_assignment=require_preferred_assignment,
                minimum_mismatches_against_avoid=minimum_mismatches_against_avoid,
                deadline=deadline,
            )
            if assignment is None:
                continue

            guidance_score = self._guidance_objective(
                assignment.assigned_center_by_cell,
                preferred_assignment,
                avoid_assignment,
            )
            return HeuristicOrbitSolveResult(
                success=True,
                status=0,
                message=(
                    "Heuristic orbit search found a structurally valid assignment."
                ),
                objective_value=guidance_score,
                mip_gap=None,
                mip_node_count=None,
                assignment=assignment,
                attempt_count=attempt_count,
            )

        if perf_counter() >= deadline:
            return HeuristicOrbitSolveResult(
                success=False,
                status=1,
                message=(
                    "Heuristic time limit reached before a valid solution was found."
                ),
                objective_value=None,
                mip_gap=None,
                mip_node_count=None,
                assignment=None,
                attempt_count=attempt_count,
            )

        return HeuristicOrbitSolveResult(
            success=False,
            status=2,
            message=(
                "Heuristic orbit search exhausted its multi-start budget without "
                "finding a valid solution."
            ),
            objective_value=None,
            mip_gap=None,
            mip_node_count=None,
            assignment=None,
            attempt_count=attempt_count,
        )


__all__ = [
    "HeuristicOrbitModel",
    "HeuristicOrbitSolveResult",
]
