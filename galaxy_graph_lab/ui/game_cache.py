from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..core import (
    DEFAULT_CPLEX_RESULTS_DIR,
    BoardSpec,
    Cell,
    CenterSpec,
    DEFAULT_DATA_DIR,
    EXACT_FLOW_SOLVER_BACKEND,
    GalaxyAssignment,
    PuzzleSolveResult,
    StoredPuzzleInstance,
    load_instance,
    save_instance,
    solve_puzzle,
    validate_assignment,
)
from ..core.generation.service import PuzzleGenerationResult


DEFAULT_GAME_CACHE_DATA_DIR = DEFAULT_DATA_DIR
DEFAULT_GAME_CACHE_RESULTS_DIR = DEFAULT_CPLEX_RESULTS_DIR


def _instance_signature(board: BoardSpec, centers: tuple[CenterSpec, ...]) -> str:
    signature = {
        "rows": board.rows,
        "cols": board.cols,
        "centers": [
            {
                "id": center.id,
                "row_coord2": center.row_coord2,
                "col_coord2": center.col_coord2,
            }
            for center in centers
        ],
    }
    return hashlib.sha1(
        json.dumps(signature, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]


def _game_instance_id(board: BoardSpec, centers: tuple[CenterSpec, ...]) -> str:
    return f"galaxy_game_{board.rows}x{board.cols}_{_instance_signature(board, centers)}"


def _matches_instance(
    instance: StoredPuzzleInstance,
    *,
    board: BoardSpec,
    centers: tuple[CenterSpec, ...],
) -> bool:
    return (
        instance.grid_size == board
        and tuple(instance.centers) == centers
    )


def _instance_path(
    data_dir: Path,
    instance_id: str,
) -> Path:
    return data_dir / f"{instance_id}.json"


def _solution_path(
    results_dir: Path,
    backend_name: str,
    instance_id: str,
) -> Path:
    return results_dir / backend_name / f"{instance_id}.json"


def _assignment_to_payload(assignment: GalaxyAssignment) -> dict[str, list[dict[str, int]]]:
    return {
        center_id: [
            {"row": cell.row, "col": cell.col}
            for cell in cells
        ]
        for center_id, cells in assignment.cells_by_center.items()
    }


def _assignment_from_payload(
    cells_by_center_payload: dict[str, list[dict[str, int]]],
) -> GalaxyAssignment:
    cells_by_center = {
        center_id: tuple(
            Cell(int(cell_data["row"]), int(cell_data["col"]))
            for cell_data in cell_entries
        )
        for center_id, cell_entries in cells_by_center_payload.items()
    }
    assigned_center_by_cell = {
        cell: center_id
        for center_id, cells in cells_by_center.items()
        for cell in cells
    }
    return GalaxyAssignment(
        assigned_center_by_cell=assigned_center_by_cell,
        cells_by_center=cells_by_center,
    )


def _build_stored_instance(
    generation_result: PuzzleGenerationResult,
    *,
    instance_id: str,
) -> StoredPuzzleInstance:
    if generation_result.puzzle is None:
        raise ValueError("A successful UI cache entry requires a generated puzzle.")
    if generation_result.difficulty_calibration is None:
        raise ValueError("A successful UI cache entry requires difficulty calibration.")

    return StoredPuzzleInstance(
        instance_id=instance_id,
        requested_difficulty=generation_result.request.difficulty,
        grid_size=generation_result.request.grid_size,
        centers=tuple(generation_result.puzzle.puzzle_data.centers),
        generation_seed=generation_result.random_seed_used,
        generation_retry_count=generation_result.retry_count,
        center_type_by_center=dict(generation_result.puzzle.center_type_by_center),
        difficulty_calibration=generation_result.difficulty_calibration,
    )


def _save_solution_result(
    instance: StoredPuzzleInstance,
    solve_result: PuzzleSolveResult,
    *,
    results_dir: Path,
) -> Path | None:
    if not solve_result.success or solve_result.assignment is None:
        return None

    validation = validate_assignment(
        instance.puzzle_data,
        solve_result.assignment.cells_by_center,
    )
    if not validation.is_valid:
        return None

    output_path = _solution_path(
        results_dir,
        solve_result.backend_name,
        instance.instance_id,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "instance_id": instance.instance_id,
        "backend_name": solve_result.backend_name,
        "status_code": solve_result.status_code,
        "status_label": solve_result.status_label,
        "message": solve_result.message,
        "objective_value": solve_result.objective_value,
        "mip_gap": solve_result.mip_gap,
        "mip_node_count": solve_result.mip_node_count,
        "solution_mode": solve_result.solution_mode,
        "preferred_assignment_count": solve_result.preferred_assignment_count,
        "matched_preference_count": solve_result.matched_preference_count,
        "mismatch_count": solve_result.mismatch_count,
        "cells_by_center": _assignment_to_payload(solve_result.assignment),
    }
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _load_solution_result(path: Path) -> PuzzleSolveResult | None:
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    cells_by_center_payload = payload.get("cells_by_center")
    if not isinstance(cells_by_center_payload, dict):
        return None

    assignment = _assignment_from_payload(cells_by_center_payload)
    return PuzzleSolveResult(
        success=True,
        backend_name=str(payload["backend_name"]),
        status_code=int(payload["status_code"]),
        status_label=str(payload["status_label"]),
        message=str(payload["message"]),
        assignment=assignment,
        objective_value=payload.get("objective_value"),
        mip_gap=payload.get("mip_gap"),
        mip_node_count=payload.get("mip_node_count"),
        solution_mode=str(payload.get("solution_mode", "plain_exact")),
        preferred_assignment_count=int(payload.get("preferred_assignment_count", 0)),
        matched_preference_count=payload.get("matched_preference_count"),
        mismatch_count=payload.get("mismatch_count"),
    )


def _load_any_cached_solution(
    instance_id: str,
    *,
    preferred_backend: str,
    results_dir: Path,
) -> PuzzleSolveResult | None:
    preferred_path = _solution_path(results_dir, preferred_backend, instance_id)
    cached_result = _load_solution_result(preferred_path)
    if cached_result is not None:
        return cached_result

    for backend_dir in sorted(results_dir.iterdir()) if results_dir.exists() else ():
        if not backend_dir.is_dir():
            continue
        candidate_path = backend_dir / f"{instance_id}.json"
        if candidate_path == preferred_path:
            continue
        cached_result = _load_solution_result(candidate_path)
        if cached_result is not None:
            return cached_result

    return None


def _load_matching_instances(
    *,
    data_dir: Path,
    board: BoardSpec,
    centers: tuple[CenterSpec, ...],
) -> tuple[StoredPuzzleInstance, ...]:
    direct_instance_id = _game_instance_id(board, centers)
    direct_instance_path = _instance_path(data_dir, direct_instance_id)
    matching_instances: list[StoredPuzzleInstance] = []
    seen_instance_ids: set[str] = set()

    if direct_instance_path.exists():
        direct_instance = load_instance(direct_instance_path)
        if _matches_instance(direct_instance, board=board, centers=centers):
            matching_instances.append(direct_instance)
            seen_instance_ids.add(direct_instance.instance_id)

    for candidate_path in sorted(data_dir.rglob("*.json")) if data_dir.exists() else ():
        if candidate_path == direct_instance_path:
            continue
        try:
            candidate_instance = load_instance(candidate_path)
        except Exception:
            continue
        if candidate_instance.instance_id in seen_instance_ids:
            continue
        if not _matches_instance(candidate_instance, board=board, centers=centers):
            continue
        matching_instances.append(candidate_instance)
        seen_instance_ids.add(candidate_instance.instance_id)

    return tuple(matching_instances)


def prepare_generated_puzzle_cache(
    generation_result: PuzzleGenerationResult,
    *,
    solver_backend: str,
    data_dir: str | Path = DEFAULT_GAME_CACHE_DATA_DIR,
    results_dir: str | Path = DEFAULT_GAME_CACHE_RESULTS_DIR,
) -> tuple[StoredPuzzleInstance, PuzzleSolveResult | None]:
    if not generation_result.success or generation_result.puzzle is None:
        raise ValueError("Only successful generated puzzles can be cached.")

    cache_data_dir = Path(data_dir)
    cache_results_dir = Path(results_dir)
    cache_data_dir.mkdir(parents=True, exist_ok=True)
    cache_results_dir.mkdir(parents=True, exist_ok=True)

    board = generation_result.request.grid_size
    centers = tuple(generation_result.puzzle.puzzle_data.centers)
    matching_instances = _load_matching_instances(
        data_dir=cache_data_dir,
        board=board,
        centers=centers,
    )
    cached_result: PuzzleSolveResult | None = None
    stored_instance: StoredPuzzleInstance | None = None

    for candidate_instance in matching_instances:
        candidate_cached_result = _load_any_cached_solution(
            candidate_instance.instance_id,
            preferred_backend=solver_backend,
            results_dir=cache_results_dir,
        )
        if candidate_cached_result is not None:
            return candidate_instance, candidate_cached_result
        if stored_instance is None:
            stored_instance = candidate_instance

    if stored_instance is None:
        instance_id = _game_instance_id(board, centers)
        instance_path = _instance_path(cache_data_dir, instance_id)
        stored_instance = _build_stored_instance(
            generation_result,
            instance_id=instance_id,
        )
        save_instance(stored_instance, instance_path)

    if solver_backend == EXACT_FLOW_SOLVER_BACKEND:
        certification = generation_result.certification
        if certification is not None and certification.solve_result.assignment is not None:
            _save_solution_result(
                stored_instance,
                certification.solve_result,
                results_dir=cache_results_dir,
            )
            return stored_instance, certification.solve_result

    solve_result = solve_puzzle(
        stored_instance.puzzle_data,
        backend=solver_backend,
    )
    _save_solution_result(
        stored_instance,
        solve_result,
        results_dir=cache_results_dir,
    )
    if solve_result.success and solve_result.assignment is not None:
        return stored_instance, solve_result
    return stored_instance, None


__all__ = [
    "DEFAULT_GAME_CACHE_DATA_DIR",
    "DEFAULT_GAME_CACHE_RESULTS_DIR",
    "prepare_generated_puzzle_cache",
]
