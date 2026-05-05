from __future__ import annotations

import json
import random
import secrets
import time
from itertools import combinations
from collections.abc import Mapping
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType

from .board import BoardSpec
from .centers import CenterSpec
from .generation import (
    CenterTypeMix,
    DifficultyCalibration,
    DifficultyProfile,
    GENERATION_DIFFICULTIES,
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_HARD,
    GENERATION_DIFFICULTY_MEDIUM,
    OverlapTargetRange,
    PuzzleGenerationRequest,
    PuzzleGenerationResult,
    difficulty_profile_for,
    generate_puzzle,
)
from .model_data import PuzzleData
from .solver_service import (
    DEFAULT_SOLVER_BACKEND,
    PARALLEL_CALLBACK_SOLVER_BACKEND,
    EXACT_FLOW_SOLVER_BACKEND,
    HEURISTIC_ORBIT_SOLVER_BACKEND,
    PuzzleSolveResult,
    SOLVER_STATUS_BACKEND_UNAVAILABLE,
    SOLVER_STATUS_ERROR,
    SOLVER_STATUS_INFEASIBLE,
    SOLVER_STATUS_SOLVED,
    SUPPORTED_SOLVER_BACKENDS,
    SOLVER_STATUS_UNSUPPORTED_BACKEND,
    solve_puzzle,
)
from .validators import validate_assignment


DEFAULT_DATA_DIR = Path("data")
DEFAULT_CPLEX_RESULTS_DIR = Path("res") / "cplex"
DEFAULT_GENERATION_RETRIES = 64
DEFAULT_GENERATION_SEED_SWEEP = 24
DEFAULT_INSTANCE_SEED_BLOCKS = 16
DEFAULT_DATASET_INSTANCES_PER_SIZE = 20
DEFAULT_DATASET_SELECTION_SOLVER_BACKEND = EXACT_FLOW_SOLVER_BACKEND
DEFAULT_DATASET_SELECTION_MIN_SOLVE_TIME_SECONDS = 0.5
DEFAULT_DATASET_SELECTION_MAX_CANDIDATE_ATTEMPTS = 256
DEFAULT_DATASET_INSTANCE_MIN_SOLVE_TIME_SECONDS = 10.0
DEFAULT_FIXED_DATASET_START_SIDE = 7
DEFAULT_FIXED_DATASET_END_SIDE = 11
DEFAULT_DATASET_REFERENCE_DIMENSION_COUNT = 5
DEFAULT_DATASET_REFERENCE_DIMENSION_STEP = 2
DEFAULT_DATASET_REFERENCE_SEARCH_MAX_SIDE = 31
DATASET_SOLVE_BACKEND_BOTH = "both"
DATASET_SOLVE_BACKEND_ALL = "all"
SUPPORTED_DATASET_SOLVER_BACKENDS = frozenset(
    set(SUPPORTED_SOLVER_BACKENDS).union(
        {DATASET_SOLVE_BACKEND_BOTH, DATASET_SOLVE_BACKEND_ALL}
    )
)
DEFAULT_DATASET_REFERENCE_SEARCH_START_SIDE_BY_DIFFICULTY = MappingProxyType(
    {
        GENERATION_DIFFICULTY_EASY: 5,
        GENERATION_DIFFICULTY_MEDIUM: 5,
        GENERATION_DIFFICULTY_HARD: 7,
    }
)
_DATASET_TARGET_AREA_PER_CENTER = {
    GENERATION_DIFFICULTY_EASY: 16,
    GENERATION_DIFFICULTY_MEDIUM: 11,
    GENERATION_DIFFICULTY_HARD: 8,
}
_DATASET_TARGET_COUNT_VARIATION = {
    GENERATION_DIFFICULTY_EASY: 1,
    GENERATION_DIFFICULTY_MEDIUM: 1,
    GENERATION_DIFFICULTY_HARD: 2,
}
_DATASET_MIN_REGION_AREA = {
    GENERATION_DIFFICULTY_EASY: 4,
    GENERATION_DIFFICULTY_MEDIUM: 3,
    GENERATION_DIFFICULTY_HARD: 2,
}


def _freeze_mapping(data: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(data))


def _freeze_path_mapping(data: Mapping[str, Path]) -> Mapping[str, Path]:
    return MappingProxyType(dict(data))


def _freeze_nested_string_mapping(
    data: Mapping[str, Mapping[str, int]] | Mapping[str, Mapping[str, float]],
) -> Mapping[str, Mapping[str, object]]:
    return MappingProxyType(
        {
            outer_key: MappingProxyType(dict(inner_mapping))
            for outer_key, inner_mapping in data.items()
        }
    )


def _json_ready(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _json_ready(inner_value)
            for key, inner_value in value.items()
        }
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _bool_as_text(value: bool) -> str:
    return "true" if value else "false"


def _grid_label(board: BoardSpec) -> str:
    return f"{board.rows}x{board.cols}"


def _square_board(side: int) -> BoardSpec:
    return BoardSpec(rows=side, cols=side)


def _instance_file_name(
    difficulty: str,
    board: BoardSpec,
    ordinal: int,
) -> str:
    return f"galaxy_{difficulty}_{_grid_label(board)}_{ordinal:03d}.json"


def _result_file_name(instance_id: str) -> str:
    return f"{instance_id}.txt"


def _backend_results_dir(results_dir: Path, solver_backend: str) -> Path:
    return results_dir / solver_backend


def _normalize_requested_counts(
    instances_per_difficulty: Mapping[str, int],
) -> Mapping[str, int]:
    normalized_counts: dict[str, int] = {
        difficulty: 0
        for difficulty in GENERATION_DIFFICULTIES
    }

    for difficulty, count in instances_per_difficulty.items():
        if difficulty not in normalized_counts:
            raise ValueError(
                "instances_per_difficulty contains an unknown difficulty: "
                f"{difficulty}."
            )
        if not isinstance(count, int) or isinstance(count, bool):
            raise TypeError("Instance counts must be plain integers.")
        if count < 0:
            raise ValueError("Instance counts must be non-negative.")
        normalized_counts[difficulty] = count

    return MappingProxyType(normalized_counts)


def _normalize_dataset_generation_grid_sizes(
    dimensions_by_difficulty: Mapping[str, tuple[BoardSpec, ...]] | None,
) -> Mapping[str, tuple[BoardSpec, ...]]:
    if dimensions_by_difficulty is None:
        raise ValueError("dimensions_by_difficulty must not be None in this helper.")

    normalized_dimensions: dict[str, tuple[BoardSpec, ...]] = {}
    for difficulty in GENERATION_DIFFICULTIES:
        grid_sizes = dimensions_by_difficulty.get(difficulty)
        if grid_sizes is None:
            normalized_dimensions[difficulty] = tuple()
            continue
        normalized_grid_sizes = tuple(grid_sizes)
        if not normalized_grid_sizes:
            normalized_dimensions[difficulty] = tuple()
            continue
        if any(not isinstance(grid_size, BoardSpec) for grid_size in normalized_grid_sizes):
            raise TypeError("Dataset generation dimensions must contain only BoardSpec values.")
        normalized_dimensions[difficulty] = normalized_grid_sizes

    return MappingProxyType(normalized_dimensions)


def _normalize_reference_search_start_sides(
    start_side_by_difficulty: Mapping[str, int] | None,
) -> Mapping[str, int]:
    if start_side_by_difficulty is None:
        return DEFAULT_DATASET_REFERENCE_SEARCH_START_SIDE_BY_DIFFICULTY

    normalized_start_sides: dict[str, int] = {}
    for difficulty in GENERATION_DIFFICULTIES:
        start_side = start_side_by_difficulty.get(difficulty)
        if not isinstance(start_side, int) or isinstance(start_side, bool):
            raise TypeError("Reference search start sides must be plain integers.")
        if start_side <= 0 or start_side % 2 == 0:
            raise ValueError("Reference search start sides must be positive odd integers.")
        normalized_start_sides[difficulty] = start_side

    return MappingProxyType(normalized_start_sides)


def _reference_window_from_anchor_side(
    anchor_side: int,
    *,
    dimension_count: int,
    dimension_step: int,
) -> tuple[BoardSpec, ...]:
    if dimension_count <= 0:
        raise ValueError("dimension_count must be positive.")
    if dimension_step <= 0:
        raise ValueError("dimension_step must be positive.")

    span = dimension_step * (dimension_count - 1)
    start_side = anchor_side - span
    if start_side > 0:
        return tuple(
            _square_board(side)
            for side in range(start_side, anchor_side + 1, dimension_step)
        )

    return tuple(
        _square_board(side)
        for side in range(anchor_side, anchor_side + span + 1, dimension_step)
    )


def _dataset_center_count_bounds(
    board: BoardSpec,
    difficulty: str,
    base_profile: DifficultyProfile,
) -> tuple[int, int]:
    area = board.rows * board.cols
    target_count = max(1, round(area / _DATASET_TARGET_AREA_PER_CENTER[difficulty]))
    variation = _DATASET_TARGET_COUNT_VARIATION[difficulty]
    feasible_max = max(1, area // _DATASET_MIN_REGION_AREA[difficulty])
    lower_bound = max(base_profile.min_center_count, target_count - variation)
    lower_bound = min(lower_bound, feasible_max)
    upper_bound = max(lower_bound, min(feasible_max, target_count + variation))
    return lower_bound, upper_bound


def _dataset_generation_profile(
    difficulty: str,
    board: BoardSpec,
) -> DifficultyProfile:
    base_profile = difficulty_profile_for(difficulty)
    min_center_count, max_center_count = _dataset_center_count_bounds(
        board,
        difficulty,
        base_profile,
    )
    return DifficultyProfile(
        difficulty=difficulty,
        allowed_grid_sizes=(board,),
        min_center_count=min_center_count,
        max_center_count=max_center_count,
        center_type_mix=CenterTypeMix(
            cell_weight=base_profile.center_type_mix.cell_weight,
            edge_weight=base_profile.center_type_mix.edge_weight,
            vertex_weight=base_profile.center_type_mix.vertex_weight,
        ),
        overlap_target_range=OverlapTargetRange(
            base_profile.overlap_target_range.min_ratio,
            base_profile.overlap_target_range.max_ratio,
        ),
        irregularity_target_range=OverlapTargetRange(
            base_profile.irregularity_target_range.min_ratio,
            base_profile.irregularity_target_range.max_ratio,
        ),
        uniqueness_required=base_profile.uniqueness_required,
        min_non_rectangular_regions=base_profile.min_non_rectangular_regions,
    )


def _effective_request(
    request: PuzzleGenerationRequest,
    random_seed: int,
) -> PuzzleGenerationRequest:
    return PuzzleGenerationRequest(
        difficulty=request.difficulty,
        grid_size=request.grid_size,
        random_seed=random_seed,
        max_generation_retries=request.max_generation_retries,
        allow_noncanonical_grid_size=request.allow_noncanonical_grid_size,
    )


def _seed_attempts(
    base_seed: int,
    seed_sweep: int,
    seed_block_count: int,
) -> tuple[int, ...]:
    attempt_budget = seed_sweep * seed_block_count
    seeds = [base_seed]
    seen = {base_seed}
    rng = random.Random(base_seed)

    while len(seeds) < attempt_budget:
        candidate_seed = rng.randrange(2**31)
        if candidate_seed in seen:
            continue
        seen.add(candidate_seed)
        seeds.append(candidate_seed)

    return tuple(seeds)


def _difficulty_calibration_from_data(data: Mapping[str, object]) -> DifficultyCalibration:
    return DifficultyCalibration(
        requested_difficulty=str(data["requested_difficulty"]),
        measured_difficulty=str(data["measured_difficulty"]),
        measured_score=float(data["measured_score"]),
        board_size_score=float(data["board_size_score"]),
        center_count_score=float(data["center_count_score"]),
        center_type_score=float(data["center_type_score"]),
        domain_overlap_score=float(data["domain_overlap_score"]),
        solver_effort_score=float(data["solver_effort_score"]),
        average_domain_overlap=float(data["average_domain_overlap"]),
        average_region_irregularity=float(data["average_region_irregularity"]),
        average_non_rectangular_irregularity=float(
            data["average_non_rectangular_irregularity"]
        ),
        max_region_irregularity=float(data["max_region_irregularity"]),
        non_rectangular_region_count=int(data["non_rectangular_region_count"]),
        overlap_within_target=bool(data["overlap_within_target"]),
        irregularity_within_target=bool(data["irregularity_within_target"]),
        profile_match=bool(data["profile_match"]),
        message=str(data["message"]),
    )


def _clear_matching_files(directory: Path, pattern: str) -> None:
    if not directory.exists():
        return
    for path in directory.glob(pattern):
        if path.is_file():
            path.unlink()


def _clear_dataset_result_artifacts(directory: Path) -> None:
    if not directory.exists():
        return
    for path in directory.rglob("galaxy_*.txt"):
        if path.is_file():
            path.unlink()
    for path in directory.rglob("summary.json"):
        if path.is_file():
            path.unlink()


def _dataset_instance_paths(data_dir: Path) -> tuple[Path, ...]:
    return tuple(sorted(data_dir.glob("galaxy_*.json")))


def _average_by_group(values_by_group: Mapping[str, list[float]]) -> Mapping[str, float]:
    return MappingProxyType(
        {
            group: (sum(values) / len(values))
            for group, values in values_by_group.items()
            if values
        }
    )


def _average_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _benchmark_generated_puzzle(
    puzzle_data: PuzzleData,
    *,
    solver_backend: str,
    solver_options: Mapping[str, object] | None = None,
) -> tuple[PuzzleSolveResult, float]:
    start_time = time.perf_counter()
    solve_result = solve_puzzle(
        puzzle_data,
        backend=solver_backend,
        options=solver_options,
    )
    solve_time = time.perf_counter() - start_time
    return solve_result, solve_time


def _screen_grid_candidate(
    *,
    difficulty: str,
    grid_size: BoardSpec,
    instance_id: str,
    seed_cursor: int,
    max_generation_retries: int,
    seed_sweep: int,
    seed_block_count: int,
    selection_solver_backend: str,
    selection_min_solve_time_seconds: float,
    selection_max_candidate_attempts: int,
    progress_callback: Callable[[str], None] | None,
    progress_label: str,
    solved_candidate_callback: Callable[
        [StoredPuzzleInstance, InstanceGenerationResult, float], None
    ]
    | None = None,
    enforce_min_solve_time: bool = True,
    solver_options: Mapping[str, object] | None = None,
) -> _ScreenedCandidateResult:
    seed_stride = seed_sweep * seed_block_count
    # Limitar intentos en búsqueda de referencia a 8 para no tardar mucho
    max_attempts = 8 if not enforce_min_solve_time else selection_max_candidate_attempts

    for candidate_attempt in range(1, max_attempts + 1):
        if progress_callback is not None:
            progress_callback(
                f"{progress_label} (candidate {candidate_attempt:03d})..."
            )

        def _generation_progress(message: str) -> None:
            if progress_callback is not None:
                progress_callback(f"{progress_label}: {message}")

        dataset_profile = _dataset_generation_profile(difficulty, grid_size)
        instance_request = PuzzleGenerationRequest(
            difficulty=difficulty,
            grid_size=grid_size,
            random_seed=seed_cursor,
            max_generation_retries=max_generation_retries,
            allow_noncanonical_grid_size=True,
        )
        
        gen_start_time = time.perf_counter()
        generation_result = generate_instance(
            instance_request,
            instance_id=instance_id,
            base_seed=seed_cursor,
            seed_sweep=seed_sweep,
            seed_block_count=seed_block_count,
            profile_override=dataset_profile,
            progress_callback=_generation_progress,
        )
        gen_time = time.perf_counter() - gen_start_time
        seed_cursor += seed_stride

        if not generation_result.success or generation_result.instance is None:
            if progress_callback is not None:
                progress_callback(
                    f"{progress_label} (candidate {candidate_attempt:03d}): generación falló (gen {gen_time:.2f}s)"
                )
            continue

        solve_result, solve_time = _benchmark_generated_puzzle(
            generation_result.instance.puzzle_data,
            solver_backend=selection_solver_backend,
            solver_options=solver_options,
        )
        if solve_result.status_label == SOLVER_STATUS_BACKEND_UNAVAILABLE:
            return _ScreenedCandidateResult(
                instance=None,
                generation_result=generation_result,
                solve_result=solve_result,
                solve_time=solve_time,
                next_seed_cursor=seed_cursor,
                candidate_attempt_count=candidate_attempt,
            )

        if (
            solve_result.success
            and solve_result.assignment is not None
        ):
            validation_result = validate_assignment(
                generation_result.instance.puzzle_data,
                solve_result.assignment.cells_by_center,
            )
            if validation_result.is_valid:
                if progress_callback is not None:
                    progress_callback(
                        f"{progress_label} (candidate {candidate_attempt:03d}): generación {gen_time:.2f}s, solver {solve_time:.2f}s"
                    )
                if solved_candidate_callback is not None:
                    solved_candidate_callback(
                        generation_result.instance,
                        generation_result,
                        solve_time,
                    )
                if enforce_min_solve_time and solve_time < selection_min_solve_time_seconds:
                    if progress_callback is not None:
                        progress_callback(
                            f"{progress_label}: solve_time {solve_time:.2f}s < {selection_min_solve_time_seconds}s, continuando..."
                        )
                    continue
                return _ScreenedCandidateResult(
                    instance=generation_result.instance,
                    generation_result=generation_result,
                    solve_result=solve_result,
                    solve_time=solve_time,
                    next_seed_cursor=seed_cursor,
                    candidate_attempt_count=candidate_attempt,
                )

    return _ScreenedCandidateResult(
        instance=None,
        generation_result=None,
        solve_result=None,
        solve_time=None,
        next_seed_cursor=seed_cursor,
        candidate_attempt_count=max_attempts,
    )


def _discover_dataset_generation_grid_sizes(
    *,
    requested_counts: Mapping[str, int],
    max_generation_retries: int,
    seed_sweep: int,
    seed_block_count: int,
    base_seed: int,
    selection_solver_backend: str,
    selection_min_solve_time_seconds: float,
    selection_max_candidate_attempts: int,
    reference_search_start_side_by_difficulty: Mapping[str, int],
    reference_search_max_side: int,
    reference_dimension_count: int,
    reference_dimension_step: int,
    progress_callback: Callable[[str], None] | None,
    solved_candidate_callback: Callable[
        [StoredPuzzleInstance, InstanceGenerationResult, float], None
    ]
    | None,
) -> tuple[
    Mapping[str, tuple[BoardSpec, ...]],
    Mapping[str, BoardSpec],
    Mapping[str, float],
    int,
    str | None,
]:
    discovered_grid_sizes: dict[str, tuple[BoardSpec, ...]] = {}
    reference_grid_size_by_difficulty: dict[str, BoardSpec] = {}
    reference_solve_time_by_difficulty: dict[str, float] = {}
    seed_cursor = base_seed

    if not any(requested_counts[difficulty] > 0 for difficulty in GENERATION_DIFFICULTIES):
        return (
            MappingProxyType(dict(discovered_grid_sizes)),
            MappingProxyType(dict(reference_grid_size_by_difficulty)),
            MappingProxyType(dict(reference_solve_time_by_difficulty)),
            seed_cursor,
            None,
        )

    threshold_difficulty = GENERATION_DIFFICULTY_HARD
    start_side = reference_search_start_side_by_difficulty[threshold_difficulty]
    if start_side > reference_search_max_side:
        return (
            MappingProxyType(dict(discovered_grid_sizes)),
            MappingProxyType(dict(reference_grid_size_by_difficulty)),
            MappingProxyType(dict(reference_solve_time_by_difficulty)),
            seed_cursor,
            (
                "Reference-dimension search range is too small for "
                f"{threshold_difficulty}: start side {start_side} exceeds max side "
                f"{reference_search_max_side}."
            ),
        )

    reference_grid_size: BoardSpec | None = None
    reference_solve_time: float | None = None
    for side in range(start_side, reference_search_max_side + 1, reference_dimension_step):
        grid_size = _square_board(side)
        screened_candidate = _screen_grid_candidate(
            difficulty=threshold_difficulty,
            grid_size=grid_size,
            instance_id=f"reference_{threshold_difficulty}_{_grid_label(grid_size)}",
            seed_cursor=seed_cursor,
            max_generation_retries=16,
            seed_sweep=8,
            seed_block_count=4,
            selection_solver_backend=selection_solver_backend,
            selection_min_solve_time_seconds=selection_min_solve_time_seconds,
            selection_max_candidate_attempts=8,
            progress_callback=progress_callback,
            progress_label=(
                "Searching reference dimension "
                f"{threshold_difficulty} {_grid_label(grid_size)}"
            ),
            solved_candidate_callback=solved_candidate_callback,
            enforce_min_solve_time=False,
            solver_options={"time_limit": 30},
        )
        seed_cursor = screened_candidate.next_seed_cursor

        if (
            screened_candidate.solve_result is not None
            and screened_candidate.solve_result.status_label
            == SOLVER_STATUS_BACKEND_UNAVAILABLE
        ):
            return (
                MappingProxyType(dict(discovered_grid_sizes)),
                MappingProxyType(dict(reference_grid_size_by_difficulty)),
                MappingProxyType(dict(reference_solve_time_by_difficulty)),
                seed_cursor,
                (
                    "Dataset generation requires backend "
                    f"'{selection_solver_backend}' for reference search, but it "
                    f"is unavailable: {screened_candidate.solve_result.message}"
                ),
            )

        if screened_candidate.instance is None or screened_candidate.solve_time is None:
            continue

        if screened_candidate.solve_time < selection_min_solve_time_seconds:
            if progress_callback is not None:
                progress_callback(
                    f"{threshold_difficulty} {_grid_label(grid_size)} "
                    f"solved in {screened_candidate.solve_time:.3f}s (below threshold, continuing...)"
                )
            continue

        reference_grid_size = grid_size
        reference_solve_time = screened_candidate.solve_time
        if progress_callback is not None:
            progress_callback(
                "Reference dimension found for "
                f"{threshold_difficulty}: {_grid_label(grid_size)} "
                f"solved in {screened_candidate.solve_time:.3f}s."
            )
        break

    if reference_grid_size is None or reference_solve_time is None:
        return (
            MappingProxyType(dict(discovered_grid_sizes)),
            MappingProxyType(dict(reference_grid_size_by_difficulty)),
            MappingProxyType(dict(reference_solve_time_by_difficulty)),
            seed_cursor,
            (
                "Could not find a hard reference dimension within the search range up to "
                f"{reference_search_max_side}x{reference_search_max_side}."
            ),
        )

    shared_window = _reference_window_from_anchor_side(
        reference_grid_size.rows,
        dimension_count=reference_dimension_count,
        dimension_step=reference_dimension_step,
    )
    for difficulty in GENERATION_DIFFICULTIES:
        if requested_counts[difficulty] <= 0:
            discovered_grid_sizes[difficulty] = tuple()
            continue
        discovered_grid_sizes[difficulty] = shared_window
        reference_grid_size_by_difficulty[difficulty] = reference_grid_size
        reference_solve_time_by_difficulty[difficulty] = reference_solve_time
        if progress_callback is not None and difficulty != threshold_difficulty:
            progress_callback(
                "Using hard reference threshold "
                f"{_grid_label(reference_grid_size)} for {difficulty}."
            )

    return (
        MappingProxyType(dict(discovered_grid_sizes)),
        MappingProxyType(dict(reference_grid_size_by_difficulty)),
        MappingProxyType(dict(reference_solve_time_by_difficulty)),
        seed_cursor,
        None,
    )


def _normalize_dataset_solver_backends(
    solver_backend: str,
) -> tuple[str, ...]:
    if solver_backend == DATASET_SOLVE_BACKEND_BOTH:
        return (
            EXACT_FLOW_SOLVER_BACKEND,
            PARALLEL_CALLBACK_SOLVER_BACKEND,
        )
    if solver_backend == DATASET_SOLVE_BACKEND_ALL:
        return (
            EXACT_FLOW_SOLVER_BACKEND,
            PARALLEL_CALLBACK_SOLVER_BACKEND,
            HEURISTIC_ORBIT_SOLVER_BACKEND,
        )
    if solver_backend not in SUPPORTED_SOLVER_BACKENDS:
        raise ValueError(f"Unsupported dataset solver backend: {solver_backend}.")
    return (solver_backend,)


@dataclass(frozen=True, slots=True)
class StoredPuzzleInstance:
    """Serialized puzzle instance together with generation metadata."""

    instance_id: str
    requested_difficulty: str
    grid_size: BoardSpec
    centers: tuple[CenterSpec, ...]
    generation_seed: int | None
    generation_retry_count: int
    center_type_by_center: Mapping[str, str]
    difficulty_calibration: DifficultyCalibration

    @property
    def puzzle_data(self) -> PuzzleData:
        return PuzzleData.from_specs(self.grid_size, self.centers)


@dataclass(frozen=True, slots=True)
class InstanceGenerationResult:
    """Structured result of generating one dataset-ready instance."""

    success: bool
    message: str
    request: PuzzleGenerationRequest
    instance: StoredPuzzleInstance | None
    generation_result: PuzzleGenerationResult | None
    generation_seed_used: int | None
    seed_attempt_count: int


@dataclass(frozen=True, slots=True)
class DataSetGenerationResult:
    """Structured result of building one on-disk dataset of instances."""

    success: bool
    message: str
    data_dir: Path
    manifest_path: Path | None
    instance_paths: tuple[Path, ...]
    requested_instances_per_difficulty: Mapping[str, int]
    instances_by_difficulty: Mapping[str, int]
    instances_by_difficulty_and_size: Mapping[str, Mapping[str, int]]
    grid_sizes_by_difficulty: Mapping[str, tuple[BoardSpec, ...]]
    reference_grid_size_by_difficulty: Mapping[str, BoardSpec]
    reference_solve_time_by_difficulty: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class HardThresholdSearchResult:
    """Empirical hard-difficulty threshold search over increasing square sizes."""

    success: bool
    message: str
    threshold_seconds: float
    solver_backend: str
    start_side: int
    max_side: int
    max_solved_grid_size: BoardSpec | None
    max_solved_solve_time: float | None
    first_exceeding_grid_size: BoardSpec | None
    first_exceeding_solve_time: float | None


@dataclass(frozen=True, slots=True)
class _ScreenedCandidateResult:
    instance: StoredPuzzleInstance | None
    generation_result: InstanceGenerationResult | None
    solve_result: PuzzleSolveResult | None
    solve_time: float | None
    next_seed_cursor: int
    candidate_attempt_count: int


@dataclass(frozen=True, slots=True)
class InstanceSolveResult:
    """Structured result of solving one stored instance."""

    instance_id: str
    instance_path: Path
    result_path: Path
    requested_difficulty: str
    measured_difficulty: str
    grid_size: BoardSpec
    solve_time: float
    is_optimal: bool
    is_structurally_valid: bool
    solve_result: PuzzleSolveResult


@dataclass(frozen=True, slots=True)
class DataSetSolveResult:
    """Structured result of resolving one dataset of stored instances."""

    success: bool
    message: str
    data_dir: Path
    results_dir: Path
    summary_path: Path | None
    records: tuple[InstanceSolveResult, ...]
    result_paths: tuple[Path, ...]
    solver_backends: tuple[str, ...]
    backend_result_dirs: Mapping[str, Path]
    backend_summary_paths: Mapping[str, Path]
    average_solve_time_by_difficulty: Mapping[str, float]
    average_solve_time_by_difficulty_and_size: Mapping[str, Mapping[str, float]]
    average_solve_time_by_backend: Mapping[str, float]
    average_solve_time_by_backend_and_difficulty: Mapping[str, Mapping[str, float]]
    status_counts_by_backend: Mapping[str, Mapping[str, int]]
    average_mip_gap_by_backend: Mapping[str, float]
    average_mip_node_count_by_backend: Mapping[str, float]
    comparison_summary: Mapping[str, object]


def generate_instance(
    request: PuzzleGenerationRequest,
    *,
    instance_id: str | None = None,
    base_seed: int | None = None,
    seed_sweep: int = DEFAULT_GENERATION_SEED_SWEEP,
    seed_block_count: int = DEFAULT_INSTANCE_SEED_BLOCKS,
    profile_override: DifficultyProfile | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> InstanceGenerationResult:
    """Generate one dataset-ready instance through repeated seeded attempts."""

    if seed_sweep <= 0:
        raise ValueError("seed_sweep must be positive.")
    if seed_block_count <= 0:
        raise ValueError("seed_block_count must be positive.")

    if base_seed is None:
        base_seed = request.random_seed
    if base_seed is None:
        base_seed = secrets.randbelow(2**31)

    if instance_id is None:
        instance_id = (
            f"galaxy_{request.difficulty}_{_grid_label(request.grid_size)}_{base_seed}"
        )

    last_generation_result: PuzzleGenerationResult | None = None
    seed_attempt_count = 0

    for effective_seed in _seed_attempts(base_seed, seed_sweep, seed_block_count):
        if progress_callback is not None:
            progress_callback(
                f"seed_attempt={seed_attempt_count + 1}/{seed_sweep * seed_block_count} "
                f"seed={effective_seed} start"
            )
        effective_request = _effective_request(request, effective_seed)
        generation_result = generate_puzzle(
            effective_request,
            profile_override=profile_override,
            progress_callback=progress_callback,
        )
        last_generation_result = generation_result
        seed_attempt_count += 1

        if (
            not generation_result.success
            or generation_result.puzzle is None
            or generation_result.difficulty_calibration is None
        ):
            if progress_callback is not None:
                progress_callback(
                    f"seed_attempt={seed_attempt_count}/{seed_sweep * seed_block_count} "
                    "result=retry"
                )
            continue

        stored_instance = StoredPuzzleInstance(
            instance_id=instance_id,
            requested_difficulty=request.difficulty,
            grid_size=request.grid_size,
            centers=generation_result.puzzle.puzzle_data.centers,
            generation_seed=effective_seed,
            generation_retry_count=generation_result.retry_count,
            center_type_by_center=MappingProxyType(
                dict(generation_result.puzzle.center_type_by_center)
            ),
            difficulty_calibration=generation_result.difficulty_calibration,
        )
        return InstanceGenerationResult(
            success=True,
            message=generation_result.message,
            request=effective_request,
            instance=stored_instance,
            generation_result=generation_result,
            generation_seed_used=effective_seed,
            seed_attempt_count=seed_attempt_count,
        )

    return InstanceGenerationResult(
        success=False,
        message=(
            "Could not generate a certified puzzle instance after repeated "
            "seeded attempts."
        ),
        request=request,
        instance=None,
        generation_result=last_generation_result,
        generation_seed_used=None,
        seed_attempt_count=seed_attempt_count,
    )


def save_instance(instance: StoredPuzzleInstance, path: str | Path) -> Path:
    """Write one generated instance to disk as JSON."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "instance_id": instance.instance_id,
        "requested_difficulty": instance.requested_difficulty,
        "grid_size": asdict(instance.grid_size),
        "centers": [asdict(center) for center in instance.centers],
        "generation_seed": instance.generation_seed,
        "generation_retry_count": instance.generation_retry_count,
        "center_type_by_center": dict(instance.center_type_by_center),
        "difficulty_calibration": asdict(instance.difficulty_calibration),
    }
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def load_instance(path: str | Path) -> StoredPuzzleInstance:
    """Load one stored puzzle instance from JSON."""

    input_path = Path(path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    grid_size = BoardSpec(**payload["grid_size"])
    centers = tuple(CenterSpec(**center_data) for center_data in payload["centers"])
    return StoredPuzzleInstance(
        instance_id=str(payload["instance_id"]),
        requested_difficulty=str(payload["requested_difficulty"]),
        grid_size=grid_size,
        centers=centers,
        generation_seed=payload["generation_seed"],
        generation_retry_count=int(payload["generation_retry_count"]),
        center_type_by_center=MappingProxyType(dict(payload["center_type_by_center"])),
        difficulty_calibration=_difficulty_calibration_from_data(
            payload["difficulty_calibration"]
        ),
    )


def find_hard_threshold_limit(
    *,
    threshold_seconds: float = DEFAULT_DATASET_SELECTION_MIN_SOLVE_TIME_SECONDS,
    solver_backend: str = DEFAULT_DATASET_SELECTION_SOLVER_BACKEND,
    start_side: int = DEFAULT_FIXED_DATASET_START_SIDE,
    max_side: int = DEFAULT_DATASET_REFERENCE_SEARCH_MAX_SIDE,
    max_generation_retries: int = DEFAULT_GENERATION_RETRIES,
    seed_sweep: int = DEFAULT_GENERATION_SEED_SWEEP,
    seed_block_count: int = DEFAULT_INSTANCE_SEED_BLOCKS,
    base_seed: int | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> HardThresholdSearchResult:
    """Search the largest hard square size whose solve time stays within a threshold."""

    if threshold_seconds < 0.0:
        raise ValueError("threshold_seconds must be non-negative.")
    if solver_backend not in SUPPORTED_SOLVER_BACKENDS:
        raise ValueError("solver_backend must name one real solver backend.")
    if start_side <= 0:
        raise ValueError("start_side must be positive.")
    if max_side < start_side:
        raise ValueError("max_side must be at least start_side.")

    if base_seed is None:
        base_seed = secrets.randbelow(2**31)

    seed_cursor = base_seed
    max_solved_grid_size: BoardSpec | None = None
    max_solved_solve_time: float | None = None

    for side in range(start_side, max_side + 1):
        grid_size = _square_board(side)
        if progress_callback is not None:
            progress_callback(
                f"Searching hard threshold dimension {_grid_label(grid_size)}..."
            )

        dataset_profile = _dataset_generation_profile(
            GENERATION_DIFFICULTY_HARD,
            grid_size,
        )
        instance_request = PuzzleGenerationRequest(
            difficulty=GENERATION_DIFFICULTY_HARD,
            grid_size=grid_size,
            random_seed=seed_cursor,
            max_generation_retries=max_generation_retries,
            allow_noncanonical_grid_size=True,
        )

        def _generation_progress(message: str) -> None:
            if progress_callback is not None:
                progress_callback(
                    f"Searching hard threshold dimension {_grid_label(grid_size)}: {message}"
                )

        generation_started_at = time.perf_counter()
        generation_result = generate_instance(
            instance_request,
            instance_id=f"hard_threshold_{_grid_label(grid_size)}",
            base_seed=seed_cursor,
            seed_sweep=seed_sweep,
            seed_block_count=seed_block_count,
            profile_override=dataset_profile,
            progress_callback=_generation_progress,
        )
        generation_time = time.perf_counter() - generation_started_at
        seed_cursor += seed_sweep * seed_block_count

        if not generation_result.success or generation_result.instance is None:
            return HardThresholdSearchResult(
                success=False,
                message=(
                    "Could not generate a valid hard instance at "
                    f"{_grid_label(grid_size)}."
                ),
                threshold_seconds=threshold_seconds,
                solver_backend=solver_backend,
                start_side=start_side,
                max_side=max_side,
                max_solved_grid_size=max_solved_grid_size,
                max_solved_solve_time=max_solved_solve_time,
                first_exceeding_grid_size=None,
                first_exceeding_solve_time=None,
            )

        solve_result, solve_time = _benchmark_generated_puzzle(
            generation_result.instance.puzzle_data,
            solver_backend=solver_backend,
        )
        if progress_callback is not None:
            progress_callback(
                "Searching hard threshold dimension "
                f"{_grid_label(grid_size)}: generación {generation_time:.2f}s, "
                f"solver {solve_time:.2f}s"
            )
        if (
            not solve_result.success
            or solve_result.assignment is None
            or not validate_assignment(
                generation_result.instance.puzzle_data,
                solve_result.assignment.cells_by_center,
            ).is_valid
        ):
            if solve_time >= threshold_seconds:
                return HardThresholdSearchResult(
                    success=True,
                    message=(
                        "Hard-threshold search completed: the threshold is first exceeded at "
                        f"{_grid_label(grid_size)}."
                    ),
                    threshold_seconds=threshold_seconds,
                    solver_backend=solver_backend,
                    start_side=start_side,
                    max_side=max_side,
                    max_solved_grid_size=max_solved_grid_size,
                    max_solved_solve_time=max_solved_solve_time,
                    first_exceeding_grid_size=grid_size,
                    first_exceeding_solve_time=solve_time,
                )
            return HardThresholdSearchResult(
                success=False,
                message=(
                    "The solver could not validate a structurally correct hard "
                    f"instance at {_grid_label(grid_size)}."
                ),
                threshold_seconds=threshold_seconds,
                solver_backend=solver_backend,
                start_side=start_side,
                max_side=max_side,
                max_solved_grid_size=max_solved_grid_size,
                max_solved_solve_time=max_solved_solve_time,
                first_exceeding_grid_size=None,
                first_exceeding_solve_time=None,
            )

        if solve_time > threshold_seconds:
            return HardThresholdSearchResult(
                success=True,
                message=(
                    "Hard-threshold search completed: the threshold is first exceeded at "
                    f"{_grid_label(grid_size)}."
                ),
                threshold_seconds=threshold_seconds,
                solver_backend=solver_backend,
                start_side=start_side,
                max_side=max_side,
                max_solved_grid_size=max_solved_grid_size,
                max_solved_solve_time=max_solved_solve_time,
                first_exceeding_grid_size=grid_size,
                first_exceeding_solve_time=solve_time,
            )

        max_solved_grid_size = grid_size
        max_solved_solve_time = solve_time

    return HardThresholdSearchResult(
        success=True,
        message=(
            "Hard-threshold search completed without exceeding the threshold "
            f"up to {_grid_label(_square_board(max_side))}."
        ),
        threshold_seconds=threshold_seconds,
        solver_backend=solver_backend,
        start_side=start_side,
        max_side=max_side,
        max_solved_grid_size=max_solved_grid_size,
        max_solved_solve_time=max_solved_solve_time,
        first_exceeding_grid_size=None,
        first_exceeding_solve_time=None,
    )


def generate_dataset(
    instances_per_difficulty: Mapping[str, int],
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    max_generation_retries: int = DEFAULT_GENERATION_RETRIES,
    seed_sweep: int = DEFAULT_GENERATION_SEED_SWEEP,
    seed_block_count: int = DEFAULT_INSTANCE_SEED_BLOCKS,
    base_seed: int | None = None,
    dimensions_by_difficulty: Mapping[str, tuple[BoardSpec, ...]] | None = None,
    selection_solver_backend: str = DEFAULT_DATASET_SELECTION_SOLVER_BACKEND,
    selection_min_solve_time_seconds: float = DEFAULT_DATASET_SELECTION_MIN_SOLVE_TIME_SECONDS,
    selection_max_candidate_attempts: int = DEFAULT_DATASET_SELECTION_MAX_CANDIDATE_ATTEMPTS,
    dataset_instance_min_solve_time_seconds: float = DEFAULT_DATASET_INSTANCE_MIN_SOLVE_TIME_SECONDS,
    reference_search_start_side_by_difficulty: Mapping[str, int] | None = None,
    reference_search_max_side: int = DEFAULT_DATASET_REFERENCE_SEARCH_MAX_SIDE,
    reference_dimension_count: int = DEFAULT_DATASET_REFERENCE_DIMENSION_COUNT,
    reference_dimension_step: int = DEFAULT_DATASET_REFERENCE_DIMENSION_STEP,
    clear_existing: bool = True,
    progress_callback: Callable[[str], None] | None = None,
) -> DataSetGenerationResult:
    """Generate one dataset after reference-size discovery and backend screening."""

    normalized_counts = _normalize_requested_counts(instances_per_difficulty)
    if selection_solver_backend not in SUPPORTED_SOLVER_BACKENDS:
        raise ValueError(
            "selection_solver_backend must name one real solver backend."
        )
    if selection_min_solve_time_seconds < 0.0:
        raise ValueError("selection_min_solve_time_seconds must be non-negative.")
    if selection_max_candidate_attempts <= 0:
        raise ValueError("selection_max_candidate_attempts must be positive.")
    if dataset_instance_min_solve_time_seconds < 0.0:
        raise ValueError("dataset_instance_min_solve_time_seconds must be non-negative.")
    if reference_search_max_side <= 0 or reference_search_max_side % 2 == 0:
        raise ValueError("reference_search_max_side must be a positive odd integer.")
    if reference_dimension_count <= 0:
        raise ValueError("reference_dimension_count must be positive.")
    if reference_dimension_step <= 0:
        raise ValueError("reference_dimension_step must be positive.")

    output_dir = Path(data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if clear_existing:
        _clear_matching_files(output_dir, "galaxy_*.json")
        manifest_path = output_dir / "manifest.json"
        if manifest_path.exists():
            manifest_path.unlink()

    if base_seed is None:
        base_seed = secrets.randbelow(2**31)

    instance_paths: list[Path] = []
    instances_by_difficulty = {
        difficulty: 0
        for difficulty in GENERATION_DIFFICULTIES
    }
    instances_by_difficulty_and_size: dict[str, dict[str, int]] = {
        difficulty: {}
        for difficulty in GENERATION_DIFFICULTIES
    }

    def _store_discovered_instance(
        instance: StoredPuzzleInstance,
        generation_result: InstanceGenerationResult,
        solve_time: float,
    ) -> None:
        difficulty = instance.requested_difficulty
        size_label = _grid_label(instance.grid_size)
        current_count = instances_by_difficulty_and_size[difficulty].get(size_label, 0)
        ordinal = current_count + 1
        instance_path = save_instance(
            instance,
            output_dir / _instance_file_name(difficulty, instance.grid_size, ordinal),
        )
        instance_paths.append(instance_path)
        instances_by_difficulty[difficulty] += 1
        instances_by_difficulty_and_size[difficulty][size_label] = ordinal
        if progress_callback is not None:
            progress_callback(
                "Generated "
                f"{difficulty} {size_label} instance {ordinal:03d} "
                f"with seed {generation_result.generation_seed_used} "
                f"after {generation_result.seed_attempt_count} seed attempts; "
                f"{selection_solver_backend} solved it in {solve_time:.3f}s."
            )

    if dimensions_by_difficulty is None:
        (
            normalized_dimensions,
            reference_grid_size_by_difficulty,
            reference_solve_time_by_difficulty,
            seed_cursor,
            discovery_error,
        ) = _discover_dataset_generation_grid_sizes(
            requested_counts=normalized_counts,
            max_generation_retries=max_generation_retries,
            seed_sweep=seed_sweep,
            seed_block_count=seed_block_count,
            base_seed=base_seed,
            selection_solver_backend=selection_solver_backend,
            selection_min_solve_time_seconds=selection_min_solve_time_seconds,
            selection_max_candidate_attempts=selection_max_candidate_attempts,
            reference_search_start_side_by_difficulty=_normalize_reference_search_start_sides(
                reference_search_start_side_by_difficulty
            ),
            reference_search_max_side=reference_search_max_side,
            reference_dimension_count=reference_dimension_count,
            reference_dimension_step=reference_dimension_step,
            progress_callback=progress_callback,
            solved_candidate_callback=_store_discovered_instance,
        )
        if discovery_error is not None:
            return DataSetGenerationResult(
                success=False,
                message=discovery_error,
                data_dir=output_dir,
                manifest_path=None,
                instance_paths=tuple(),
                requested_instances_per_difficulty=normalized_counts,
                instances_by_difficulty=MappingProxyType(
                    {difficulty: 0 for difficulty in GENERATION_DIFFICULTIES}
                ),
                instances_by_difficulty_and_size=_freeze_nested_string_mapping(
                    {
                        difficulty: {}
                        for difficulty in GENERATION_DIFFICULTIES
                    }
                ),
                grid_sizes_by_difficulty=normalized_dimensions,
                reference_grid_size_by_difficulty=reference_grid_size_by_difficulty,
                reference_solve_time_by_difficulty=reference_solve_time_by_difficulty,
            )
    else:
        normalized_dimensions = _normalize_dataset_generation_grid_sizes(
            dimensions_by_difficulty
        )
        reference_grid_size_by_difficulty = MappingProxyType({})
        reference_solve_time_by_difficulty = MappingProxyType({})
        seed_cursor = base_seed
    for difficulty in GENERATION_DIFFICULTIES:
        requested_count = normalized_counts[difficulty]
        for grid_size in normalized_dimensions[difficulty]:
            size_label = _grid_label(grid_size)
            current_count = instances_by_difficulty_and_size[difficulty].get(size_label, 0)
            if size_label not in instances_by_difficulty_and_size[difficulty]:
                instances_by_difficulty_and_size[difficulty][size_label] = current_count

            for ordinal in range(current_count + 1, requested_count + 1):
                screened_candidate = _screen_grid_candidate(
                    difficulty=difficulty,
                    grid_size=grid_size,
                    instance_id=f"galaxy_{difficulty}_{size_label}_{ordinal:03d}",
                    seed_cursor=seed_cursor,
                    max_generation_retries=max_generation_retries,
                    seed_sweep=seed_sweep,
                    seed_block_count=seed_block_count,
                    selection_solver_backend=selection_solver_backend,
                    selection_min_solve_time_seconds=dataset_instance_min_solve_time_seconds,
                    selection_max_candidate_attempts=selection_max_candidate_attempts,
                    progress_callback=progress_callback,
                    progress_label=(
                        "Generating "
                        f"{difficulty} {size_label} instance {ordinal:03d}"
                    ),
                )
                seed_cursor = screened_candidate.next_seed_cursor

                if (
                    screened_candidate.solve_result is not None
                    and screened_candidate.solve_result.status_label
                    == SOLVER_STATUS_BACKEND_UNAVAILABLE
                ):
                    return DataSetGenerationResult(
                        success=False,
                        message=(
                            "Dataset generation requires backend "
                            f"'{selection_solver_backend}' for screening, but it "
                            f"is unavailable: {screened_candidate.solve_result.message}"
                        ),
                        data_dir=output_dir,
                        manifest_path=None,
                        instance_paths=tuple(instance_paths),
                        requested_instances_per_difficulty=normalized_counts,
                        instances_by_difficulty=MappingProxyType(
                            dict(instances_by_difficulty)
                        ),
                        instances_by_difficulty_and_size=_freeze_nested_string_mapping(
                            instances_by_difficulty_and_size
                        ),
                        grid_sizes_by_difficulty=normalized_dimensions,
                        reference_grid_size_by_difficulty=reference_grid_size_by_difficulty,
                        reference_solve_time_by_difficulty=reference_solve_time_by_difficulty,
                    )

                if (
                    screened_candidate.instance is None
                    or screened_candidate.generation_result is None
                    or screened_candidate.solve_time is None
                ):
                    if progress_callback is not None:
                        progress_callback(
                            "Failed "
                            f"{difficulty} {size_label} instance {ordinal:03d} "
                            f"after {screened_candidate.candidate_attempt_count} screened candidates."
                        )
                    return DataSetGenerationResult(
                        success=False,
                        message=(
                            "Could not generate the requested dataset coverage under "
                            "the backend-screened generation rule: "
                            f"{difficulty} {_grid_label(grid_size)} "
                            f"instance {ordinal:03d}."
                        ),
                        data_dir=output_dir,
                        manifest_path=None,
                        instance_paths=tuple(instance_paths),
                        requested_instances_per_difficulty=normalized_counts,
                        instances_by_difficulty=MappingProxyType(
                            dict(instances_by_difficulty)
                        ),
                        instances_by_difficulty_and_size=_freeze_nested_string_mapping(
                            instances_by_difficulty_and_size
                        ),
                        grid_sizes_by_difficulty=normalized_dimensions,
                        reference_grid_size_by_difficulty=reference_grid_size_by_difficulty,
                        reference_solve_time_by_difficulty=reference_solve_time_by_difficulty,
                    )

                instance_path = save_instance(
                    screened_candidate.instance,
                    output_dir / _instance_file_name(difficulty, grid_size, ordinal),
                )
                instance_paths.append(instance_path)
                if progress_callback is not None:
                    progress_callback(
                        "Generated "
                        f"{difficulty} {size_label} instance {ordinal:03d} "
                        f"with seed {screened_candidate.generation_result.generation_seed_used} "
                        f"after {screened_candidate.generation_result.seed_attempt_count} seed attempts; "
                        f"{selection_solver_backend} solved it in {screened_candidate.solve_time:.3f}s."
                    )
                instances_by_difficulty[difficulty] += 1
                instances_by_difficulty_and_size[difficulty][size_label] = ordinal

    manifest_path = output_dir / "manifest.json"
    manifest_payload = {
        "requested_instances_per_difficulty_per_size": dict(normalized_counts),
        "dataset_grid_sizes_by_difficulty": {
            difficulty: [_grid_label(grid_size) for grid_size in grid_sizes]
            for difficulty, grid_sizes in normalized_dimensions.items()
        },
        "reference_grid_size_by_difficulty": {
            difficulty: _grid_label(grid_size)
            for difficulty, grid_size in reference_grid_size_by_difficulty.items()
        },
        "reference_solve_time_by_difficulty": dict(reference_solve_time_by_difficulty),
        "instances_by_difficulty": instances_by_difficulty,
        "instances_by_difficulty_and_size": instances_by_difficulty_and_size,
        "selection_solver_backend": selection_solver_backend,
        "reference_search_min_solve_time_seconds": selection_min_solve_time_seconds,
        "dataset_instance_min_solve_time_seconds": dataset_instance_min_solve_time_seconds,
        "instance_files": [path.name for path in instance_paths],
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return DataSetGenerationResult(
        success=True,
        message="Dataset generated successfully.",
        data_dir=output_dir,
        manifest_path=manifest_path,
        instance_paths=tuple(instance_paths),
        requested_instances_per_difficulty=normalized_counts,
        instances_by_difficulty=MappingProxyType(dict(instances_by_difficulty)),
        instances_by_difficulty_and_size=_freeze_nested_string_mapping(
            instances_by_difficulty_and_size
        ),
        grid_sizes_by_difficulty=normalized_dimensions,
        reference_grid_size_by_difficulty=reference_grid_size_by_difficulty,
        reference_solve_time_by_difficulty=reference_solve_time_by_difficulty,
    )


def solve_instance(
    instance: StoredPuzzleInstance,
    *,
    instance_path: str | Path,
    results_dir: str | Path = DEFAULT_CPLEX_RESULTS_DIR,
    solver_backend: str = DEFAULT_SOLVER_BACKEND,
) -> InstanceSolveResult:
    """Solve one stored instance and prepare its cplex-style result artifact."""

    source_path = Path(instance_path)
    output_dir = Path(results_dir)
    backend_output_dir = _backend_results_dir(output_dir, solver_backend)
    backend_output_dir.mkdir(parents=True, exist_ok=True)
    result_path = backend_output_dir / _result_file_name(instance.instance_id)

    start_time = time.perf_counter()
    solve_result = solve_puzzle(instance.puzzle_data, backend=solver_backend)
    solve_time = time.perf_counter() - start_time

    is_optimal = False
    is_structurally_valid = False
    if solve_result.success and solve_result.assignment is not None:
        validation_result = validate_assignment(
            instance.puzzle_data,
            solve_result.assignment.cells_by_center,
        )
        is_structurally_valid = validation_result.is_valid
        is_optimal = (
            solve_result.status_label == SOLVER_STATUS_SOLVED
            and is_structurally_valid
        )

    result_lines = [
        f"solveTime={solve_time:.6f}",
        f"isOptimal={_bool_as_text(is_optimal)}",
        f"isStructurallyValid={_bool_as_text(is_structurally_valid)}",
        f"statusLabel={solve_result.status_label}",
        f"statusCode={solve_result.status_code}",
        f"backend={solve_result.backend_name}",
        f"requestedDifficulty={instance.requested_difficulty}",
        f"measuredDifficulty={instance.difficulty_calibration.measured_difficulty}",
        f"gridSize={_grid_label(instance.grid_size)}",
    ]
    if solve_result.objective_value is not None:
        result_lines.append(f"objectiveValue={solve_result.objective_value}")
    if solve_result.mip_gap is not None:
        result_lines.append(f"mipGap={solve_result.mip_gap}")
    if solve_result.mip_node_count is not None:
        result_lines.append(f"mipNodeCount={solve_result.mip_node_count}")

    result_path.write_text("\n".join(result_lines) + "\n", encoding="utf-8")

    return InstanceSolveResult(
        instance_id=instance.instance_id,
        instance_path=source_path,
        result_path=result_path,
        requested_difficulty=instance.requested_difficulty,
        measured_difficulty=instance.difficulty_calibration.measured_difficulty,
        grid_size=instance.grid_size,
        solve_time=solve_time,
        is_optimal=is_optimal,
        is_structurally_valid=is_structurally_valid,
        solve_result=solve_result,
    )


def solve_dataset(
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    results_dir: str | Path = DEFAULT_CPLEX_RESULTS_DIR,
    solver_backend: str = DEFAULT_SOLVER_BACKEND,
    clear_existing: bool = True,
) -> DataSetSolveResult:
    """Resolve the stored dataset and write one cplex-style text file per instance."""

    input_dir = Path(data_dir)
    output_dir = Path(results_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_solver_backends = _normalize_dataset_solver_backends(solver_backend)
    backend_result_dirs = _freeze_path_mapping(
        {
            backend_name: _backend_results_dir(output_dir, backend_name)
            for backend_name in selected_solver_backends
        }
    )

    if clear_existing:
        _clear_dataset_result_artifacts(output_dir)

    instance_paths = _dataset_instance_paths(input_dir)
    if not instance_paths:
        return DataSetSolveResult(
            success=False,
            message="The dataset directory does not contain any stored instances.",
            data_dir=input_dir,
            results_dir=output_dir,
            summary_path=None,
            records=(),
            result_paths=(),
            solver_backends=selected_solver_backends,
            backend_result_dirs=backend_result_dirs,
            backend_summary_paths=MappingProxyType({}),
            average_solve_time_by_difficulty=MappingProxyType({}),
            average_solve_time_by_difficulty_and_size=MappingProxyType({}),
            average_solve_time_by_backend=MappingProxyType({}),
            average_solve_time_by_backend_and_difficulty=MappingProxyType({}),
            status_counts_by_backend=MappingProxyType({}),
            average_mip_gap_by_backend=MappingProxyType({}),
            average_mip_node_count_by_backend=MappingProxyType({}),
            comparison_summary=MappingProxyType({}),
        )

    records: list[InstanceSolveResult] = []
    times_by_difficulty: dict[str, list[float]] = {}
    times_by_difficulty_and_size: dict[str, dict[str, list[float]]] = {}
    times_by_backend: dict[str, list[float]] = {}
    times_by_backend_and_difficulty: dict[str, dict[str, list[float]]] = {}
    times_by_backend_and_difficulty_and_size: dict[str, dict[str, dict[str, list[float]]]] = {}
    status_counts_by_backend: dict[str, dict[str, int]] = {}
    mip_gaps_by_backend: dict[str, list[float]] = {}
    mip_node_counts_by_backend: dict[str, list[float]] = {}
    records_by_instance_and_backend: dict[str, dict[str, InstanceSolveResult]] = {}

    for instance_path in instance_paths:
        instance = load_instance(instance_path)
        for concrete_backend in selected_solver_backends:
            record = solve_instance(
                instance,
                instance_path=instance_path,
                results_dir=output_dir,
                solver_backend=concrete_backend,
            )
            records.append(record)
            records_by_instance_and_backend.setdefault(record.instance_id, {})[
                concrete_backend
            ] = record
            times_by_difficulty.setdefault(record.requested_difficulty, []).append(
                record.solve_time
            )
            size_label = _grid_label(record.grid_size)
            times_by_difficulty_and_size.setdefault(
                record.requested_difficulty,
                {},
            ).setdefault(size_label, []).append(record.solve_time)
            backend_name = record.solve_result.backend_name
            times_by_backend.setdefault(backend_name, []).append(record.solve_time)
            times_by_backend_and_difficulty.setdefault(
                backend_name,
                {},
            ).setdefault(record.requested_difficulty, []).append(record.solve_time)
            times_by_backend_and_difficulty_and_size.setdefault(
                backend_name,
                {},
            ).setdefault(record.requested_difficulty, {}).setdefault(
                size_label,
                [],
            ).append(record.solve_time)
            status_counts_by_backend.setdefault(backend_name, {}).setdefault(
                record.solve_result.status_label,
                0,
            )
            status_counts_by_backend[backend_name][record.solve_result.status_label] += 1
            if record.solve_result.mip_gap is not None:
                mip_gaps_by_backend.setdefault(backend_name, []).append(
                    record.solve_result.mip_gap
                )
            if record.solve_result.mip_node_count is not None:
                mip_node_counts_by_backend.setdefault(backend_name, []).append(
                    float(record.solve_result.mip_node_count)
                )

    average_solve_time_by_difficulty = _average_by_group(times_by_difficulty)
    average_solve_time_by_difficulty_and_size = _freeze_nested_string_mapping(
        {
            difficulty: {
                size_label: (sum(values) / len(values))
                for size_label, values in size_map.items()
            }
            for difficulty, size_map in times_by_difficulty_and_size.items()
        }
    )
    average_solve_time_by_backend = _average_by_group(times_by_backend)
    average_solve_time_by_backend_and_difficulty = _freeze_nested_string_mapping(
        {
            backend_name: {
                difficulty: (sum(values) / len(values))
                for difficulty, values in difficulty_map.items()
            }
            for backend_name, difficulty_map in times_by_backend_and_difficulty.items()
        }
    )
    frozen_status_counts_by_backend = _freeze_nested_string_mapping(
        status_counts_by_backend
    )
    average_mip_gap_by_backend = MappingProxyType(
        {
            backend_name: average_gap
            for backend_name, gaps in mip_gaps_by_backend.items()
            if (average_gap := _average_or_none(gaps)) is not None
        }
    )
    average_mip_node_count_by_backend = MappingProxyType(
        {
            backend_name: average_nodes
            for backend_name, nodes in mip_node_counts_by_backend.items()
            if (average_nodes := _average_or_none(nodes)) is not None
        }
    )

    backend_summary_paths: dict[str, Path] = {}
    for backend_name in selected_solver_backends:
        backend_dir = backend_result_dirs[backend_name]
        backend_dir.mkdir(parents=True, exist_ok=True)
        backend_summary_path = backend_dir / "summary.json"
        backend_average_solve_time_by_difficulty = {
            difficulty: (sum(values) / len(values))
            for difficulty, values in times_by_backend_and_difficulty.get(
                backend_name,
                {},
            ).items()
        }
        backend_average_solve_time_by_difficulty_and_size = {
            difficulty: {
                size_label: (sum(values) / len(values))
                for size_label, values in size_map.items()
            }
            for difficulty, size_map in times_by_backend_and_difficulty_and_size.get(
                backend_name,
                {},
            ).items()
        }
        backend_status_counts = dict(status_counts_by_backend.get(backend_name, {}))
        backend_summary_payload = {
            "backend": backend_name,
            "instance_count": sum(backend_status_counts.values()),
            "average_solve_time": _average_or_none(times_by_backend.get(backend_name, [])),
            "average_solve_time_by_difficulty": backend_average_solve_time_by_difficulty,
            "average_solve_time_by_difficulty_and_size": (
                backend_average_solve_time_by_difficulty_and_size
            ),
            "status_counts": backend_status_counts,
            "solved_count": backend_status_counts.get(SOLVER_STATUS_SOLVED, 0),
            "infeasible_count": backend_status_counts.get(SOLVER_STATUS_INFEASIBLE, 0),
            "backend_unavailable_count": backend_status_counts.get(
                SOLVER_STATUS_BACKEND_UNAVAILABLE,
                0,
            ),
            "solver_error_count": backend_status_counts.get(SOLVER_STATUS_ERROR, 0),
            "unsupported_backend_count": backend_status_counts.get(
                SOLVER_STATUS_UNSUPPORTED_BACKEND,
                0,
            ),
            "average_mip_gap": average_mip_gap_by_backend.get(backend_name),
            "average_mip_node_count": average_mip_node_count_by_backend.get(
                backend_name
            ),
            "result_files": sorted(
                record.result_path.name
                for record in records
                if record.solve_result.backend_name == backend_name
            ),
        }
        backend_summary_path.write_text(
            json.dumps(backend_summary_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        backend_summary_paths[backend_name] = backend_summary_path

    if len(selected_solver_backends) >= 2:
        baseline_backend = selected_solver_backends[0]
        comparison_backend = selected_solver_backends[1]

        def _pairwise_summary(
            left_backend: str,
            right_backend: str,
        ) -> Mapping[str, object]:
            time_differences_by_difficulty: dict[str, list[float]] = {}
            instances_solved_by_both = 0
            success_status_disagreement_count = 0
            structural_validity_disagreement_count = 0

            for record_map in records_by_instance_and_backend.values():
                left_record = record_map.get(left_backend)
                right_record = record_map.get(right_backend)
                if left_record is None or right_record is None:
                    continue
                if (
                    left_record.solve_result.status_label == SOLVER_STATUS_SOLVED
                    and right_record.solve_result.status_label == SOLVER_STATUS_SOLVED
                ):
                    instances_solved_by_both += 1
                if left_record.solve_result.success != right_record.solve_result.success:
                    success_status_disagreement_count += 1
                if left_record.is_structurally_valid != right_record.is_structurally_valid:
                    structural_validity_disagreement_count += 1
                time_differences_by_difficulty.setdefault(
                    left_record.requested_difficulty,
                    [],
                ).append(right_record.solve_time - left_record.solve_time)

            return _freeze_mapping(
                {
                    "time_difference_reference_pair": (
                        left_backend,
                        right_backend,
                    ),
                    "instances_solved_by_both": instances_solved_by_both,
                    "average_time_difference_by_difficulty": MappingProxyType(
                        {
                            difficulty: (sum(values) / len(values))
                            for difficulty, values in time_differences_by_difficulty.items()
                            if values
                        }
                    ),
                    "success_status_disagreement_count": success_status_disagreement_count,
                    "structural_validity_disagreement_count": (
                        structural_validity_disagreement_count
                    ),
                }
            )

        pairwise_comparison = {
            f"{left_backend}__vs__{right_backend}": dict(
                _pairwise_summary(
                    left_backend,
                    right_backend,
                )
            )
            for left_backend, right_backend in combinations(selected_solver_backends, 2)
        }
        reference_pair_summary = pairwise_comparison[
            f"{baseline_backend}__vs__{comparison_backend}"
        ]
        comparison_summary = _freeze_mapping(
            {
                **dict(reference_pair_summary),
                "pairwise": MappingProxyType(dict(pairwise_comparison)),
            }
        )
    else:
        comparison_summary = MappingProxyType({})

    summary_path = output_dir / "summary.json"
    summary_payload = {
        "instance_count": len(records),
        "solver_backends": list(selected_solver_backends),
        "backend_result_directories": {
            backend_name: str(path)
            for backend_name, path in backend_result_dirs.items()
        },
        "backend_summaries": {
            backend_name: str(path)
            for backend_name, path in backend_summary_paths.items()
        },
        "average_solve_time_by_difficulty": dict(average_solve_time_by_difficulty),
        "average_solve_time_by_difficulty_and_size": {
            difficulty: dict(size_map)
            for difficulty, size_map in average_solve_time_by_difficulty_and_size.items()
        },
        "average_solve_time_by_backend": dict(average_solve_time_by_backend),
        "average_solve_time_by_backend_and_difficulty": {
            backend_name: dict(difficulty_map)
            for backend_name, difficulty_map in average_solve_time_by_backend_and_difficulty.items()
        },
        "status_counts_by_backend": {
            backend_name: dict(status_counts)
            for backend_name, status_counts in frozen_status_counts_by_backend.items()
        },
        "average_mip_gap_by_backend": dict(average_mip_gap_by_backend),
        "average_mip_node_count_by_backend": dict(average_mip_node_count_by_backend),
        "comparison": _json_ready(comparison_summary),
        "result_files": [str(record.result_path.relative_to(output_dir)) for record in records],
    }
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return DataSetSolveResult(
        success=True,
        message="Dataset solved successfully.",
        data_dir=input_dir,
        results_dir=output_dir,
        summary_path=summary_path,
        records=tuple(records),
        result_paths=tuple(record.result_path for record in records),
        solver_backends=selected_solver_backends,
        backend_result_dirs=backend_result_dirs,
        backend_summary_paths=_freeze_path_mapping(backend_summary_paths),
        average_solve_time_by_difficulty=average_solve_time_by_difficulty,
        average_solve_time_by_difficulty_and_size=average_solve_time_by_difficulty_and_size,
        average_solve_time_by_backend=average_solve_time_by_backend,
        average_solve_time_by_backend_and_difficulty=average_solve_time_by_backend_and_difficulty,
        status_counts_by_backend=frozen_status_counts_by_backend,
        average_mip_gap_by_backend=average_mip_gap_by_backend,
        average_mip_node_count_by_backend=average_mip_node_count_by_backend,
        comparison_summary=comparison_summary,
    )


__all__ = [
    "DEFAULT_CPLEX_RESULTS_DIR",
    "DEFAULT_DATA_DIR",
    "DEFAULT_DATASET_INSTANCES_PER_SIZE",
    "DEFAULT_DATASET_INSTANCE_MIN_SOLVE_TIME_SECONDS",
    "DEFAULT_FIXED_DATASET_END_SIDE",
    "DEFAULT_FIXED_DATASET_START_SIDE",
    "DEFAULT_DATASET_REFERENCE_DIMENSION_COUNT",
    "DEFAULT_DATASET_REFERENCE_DIMENSION_STEP",
    "DEFAULT_DATASET_REFERENCE_SEARCH_MAX_SIDE",
    "DEFAULT_DATASET_REFERENCE_SEARCH_START_SIDE_BY_DIFFICULTY",
    "DEFAULT_DATASET_SELECTION_MAX_CANDIDATE_ATTEMPTS",
    "DEFAULT_DATASET_SELECTION_MIN_SOLVE_TIME_SECONDS",
    "DEFAULT_DATASET_SELECTION_SOLVER_BACKEND",
    "DEFAULT_GENERATION_RETRIES",
    "DEFAULT_GENERATION_SEED_SWEEP",
    "DEFAULT_INSTANCE_SEED_BLOCKS",
    "DATASET_SOLVE_BACKEND_ALL",
    "DATASET_SOLVE_BACKEND_BOTH",
    "DataSetGenerationResult",
    "DataSetSolveResult",
    "HardThresholdSearchResult",
    "InstanceGenerationResult",
    "InstanceSolveResult",
    "StoredPuzzleInstance",
    "find_hard_threshold_limit",
    "SUPPORTED_DATASET_SOLVER_BACKENDS",
    "generate_dataset",
    "generate_instance",
    "load_instance",
    "save_instance",
    "solve_dataset",
    "solve_instance",
]
