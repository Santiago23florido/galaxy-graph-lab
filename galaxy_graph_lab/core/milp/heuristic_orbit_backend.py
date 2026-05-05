from __future__ import annotations

from collections.abc import Mapping

from ..board import Cell
from ..model_data import PuzzleData
from .heuristic_orbit_model import (
    HeuristicOrbitModel,
    HeuristicOrbitSolveResult,
)


def _resolve_time_limit(options: Mapping[str, object] | None) -> float:
    if options is None:
        raise ValueError("The heuristic backend requires a time_limit option.")

    for key in ("time_limit", "timelimit", "timeLimit"):
        raw_value = options.get(key)
        if raw_value is None:
            continue
        if not isinstance(raw_value, int | float) or isinstance(raw_value, bool):
            raise TypeError(f"Solver option '{key}' must be numeric.")
        if raw_value <= 0:
            raise ValueError(f"Solver option '{key}' must be positive.")
        return float(raw_value)

    raise ValueError("The heuristic backend requires a positive time_limit option.")


def _resolve_random_seed(options: Mapping[str, object] | None) -> int | None:
    if options is None:
        return None

    for key in ("random_seed", "seed"):
        raw_value = options.get(key)
        if raw_value is None:
            continue
        if not isinstance(raw_value, int) or isinstance(raw_value, bool):
            raise TypeError(f"Solver option '{key}' must be a plain integer.")
        return int(raw_value)
    return None


def _resolve_max_starts(options: Mapping[str, object] | None) -> int | None:
    if options is None:
        return None

    for key in ("max_starts", "restart_limit", "max_restarts"):
        raw_value = options.get(key)
        if raw_value is None:
            continue
        if not isinstance(raw_value, int) or isinstance(raw_value, bool):
            raise TypeError(f"Solver option '{key}' must be a plain integer.")
        if raw_value <= 0:
            raise ValueError(f"Solver option '{key}' must be positive.")
        return int(raw_value)
    return None


def solve_heuristic_orbit_model(
    model: HeuristicOrbitModel | PuzzleData,
    options: Mapping[str, object] | None = None,
    *,
    preferred_assignment_by_cell: Mapping[Cell, str] | None = None,
    avoid_assignment_by_cell: Mapping[Cell, str] | None = None,
    minimum_mismatches_against_avoid: int | None = None,
    require_preferred_assignment: bool = False,
) -> HeuristicOrbitSolveResult:
    """Solve the puzzle with the orbit-based constructive heuristic backend."""

    if isinstance(model, PuzzleData):
        model = HeuristicOrbitModel.from_puzzle_data(model)

    return model.solve(
        time_limit=_resolve_time_limit(options),
        preferred_assignment_by_cell=preferred_assignment_by_cell,
        avoid_assignment_by_cell=avoid_assignment_by_cell,
        minimum_mismatches_against_avoid=minimum_mismatches_against_avoid,
        require_preferred_assignment=require_preferred_assignment,
        random_seed=_resolve_random_seed(options),
        max_starts=_resolve_max_starts(options),
    )


__all__ = ["solve_heuristic_orbit_model"]
