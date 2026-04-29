from __future__ import annotations

import json
import random
import secrets
import time
from collections.abc import Mapping
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType

from .board import BoardSpec
from .centers import CenterSpec
from .generation import (
    DifficultyCalibration,
    GENERATION_DIFFICULTIES,
    PuzzleGenerationRequest,
    PuzzleGenerationResult,
    difficulty_profile_for,
    generate_puzzle,
)
from .model_data import PuzzleData
from .solver_service import PuzzleSolveResult, SOLVER_STATUS_SOLVED, solve_puzzle
from .validators import validate_assignment


DEFAULT_DATA_DIR = Path("data")
DEFAULT_CPLEX_RESULTS_DIR = Path("res") / "cplex"
DEFAULT_GENERATION_RETRIES = 64
DEFAULT_GENERATION_SEED_SWEEP = 24
DEFAULT_INSTANCE_SEED_BLOCKS = 16


def _freeze_mapping(data: Mapping[str, object]) -> Mapping[str, object]:
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


def _bool_as_text(value: bool) -> str:
    return "true" if value else "false"


def _grid_label(board: BoardSpec) -> str:
    return f"{board.rows}x{board.cols}"


def _instance_file_name(
    difficulty: str,
    board: BoardSpec,
    ordinal: int,
) -> str:
    return f"galaxy_{difficulty}_{_grid_label(board)}_{ordinal:03d}.json"


def _result_file_name(instance_id: str) -> str:
    return f"{instance_id}.txt"


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


def _effective_request(
    request: PuzzleGenerationRequest,
    random_seed: int,
) -> PuzzleGenerationRequest:
    return PuzzleGenerationRequest(
        difficulty=request.difficulty,
        grid_size=request.grid_size,
        random_seed=random_seed,
        max_generation_retries=request.max_generation_retries,
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
    average_solve_time_by_difficulty: Mapping[str, float]
    average_solve_time_by_difficulty_and_size: Mapping[str, Mapping[str, float]]


def generate_instance(
    request: PuzzleGenerationRequest,
    *,
    instance_id: str | None = None,
    base_seed: int | None = None,
    seed_sweep: int = DEFAULT_GENERATION_SEED_SWEEP,
    seed_block_count: int = DEFAULT_INSTANCE_SEED_BLOCKS,
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
        effective_request = _effective_request(request, effective_seed)
        generation_result = generate_puzzle(effective_request)
        last_generation_result = generation_result
        seed_attempt_count += 1

        if (
            not generation_result.success
            or generation_result.puzzle is None
            or generation_result.difficulty_calibration is None
        ):
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


def generate_dataset(
    instances_per_difficulty: Mapping[str, int],
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    max_generation_retries: int = DEFAULT_GENERATION_RETRIES,
    seed_sweep: int = DEFAULT_GENERATION_SEED_SWEEP,
    seed_block_count: int = DEFAULT_INSTANCE_SEED_BLOCKS,
    base_seed: int | None = None,
    clear_existing: bool = True,
    progress_callback: Callable[[str], None] | None = None,
) -> DataSetGenerationResult:
    """Generate one dataset that covers every grid size allowed by each difficulty."""

    normalized_counts = _normalize_requested_counts(instances_per_difficulty)
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

    seed_cursor = base_seed
    seed_stride = seed_sweep * seed_block_count
    for difficulty in GENERATION_DIFFICULTIES:
        profile = difficulty_profile_for(difficulty)
        requested_count = normalized_counts[difficulty]
        for grid_size in profile.allowed_grid_sizes:
            size_label = _grid_label(grid_size)
            instances_by_difficulty_and_size[difficulty][size_label] = 0

            for ordinal in range(1, requested_count + 1):
                if progress_callback is not None:
                    progress_callback(
                        "Generating "
                        f"{difficulty} {size_label} instance {ordinal:03d}..."
                    )
                instance_request = PuzzleGenerationRequest(
                    difficulty=difficulty,
                    grid_size=grid_size,
                    random_seed=seed_cursor,
                    max_generation_retries=max_generation_retries,
                )
                generation_result = generate_instance(
                    instance_request,
                    instance_id=(
                        f"galaxy_{difficulty}_{size_label}_{ordinal:03d}"
                    ),
                    base_seed=seed_cursor,
                    seed_sweep=seed_sweep,
                    seed_block_count=seed_block_count,
                )
                seed_cursor += seed_stride

                if not generation_result.success or generation_result.instance is None:
                    if progress_callback is not None:
                        progress_callback(
                            "Failed "
                            f"{difficulty} {size_label} instance {ordinal:03d} "
                            f"after {generation_result.seed_attempt_count} seed attempts."
                        )
                    return DataSetGenerationResult(
                        success=False,
                        message=(
                            "Could not generate the requested dataset coverage: "
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
                    )

                instance_path = save_instance(
                    generation_result.instance,
                    output_dir / _instance_file_name(difficulty, grid_size, ordinal),
                )
                instance_paths.append(instance_path)
                if progress_callback is not None:
                    progress_callback(
                        "Generated "
                        f"{difficulty} {size_label} instance {ordinal:03d} "
                        f"with seed {generation_result.generation_seed_used} "
                        f"after {generation_result.seed_attempt_count} seed attempts."
                    )
                instances_by_difficulty[difficulty] += 1
                instances_by_difficulty_and_size[difficulty][size_label] += 1

    manifest_path = output_dir / "manifest.json"
    manifest_payload = {
        "requested_instances_per_difficulty_per_size": dict(normalized_counts),
        "instances_by_difficulty": instances_by_difficulty,
        "instances_by_difficulty_and_size": instances_by_difficulty_and_size,
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
    )


def solve_instance(
    instance: StoredPuzzleInstance,
    *,
    instance_path: str | Path,
    results_dir: str | Path = DEFAULT_CPLEX_RESULTS_DIR,
) -> InstanceSolveResult:
    """Solve one stored instance and prepare its cplex-style result artifact."""

    source_path = Path(instance_path)
    output_dir = Path(results_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / _result_file_name(instance.instance_id)

    start_time = time.perf_counter()
    solve_result = solve_puzzle(instance.puzzle_data)
    solve_time = time.perf_counter() - start_time

    is_optimal = False
    if solve_result.success and solve_result.assignment is not None:
        validation_result = validate_assignment(
            instance.puzzle_data,
            solve_result.assignment.cells_by_center,
        )
        is_optimal = (
            solve_result.status_label == SOLVER_STATUS_SOLVED
            and validation_result.is_valid
        )

    result_lines = [
        f"solveTime={solve_time:.6f}",
        f"isOptimal={_bool_as_text(is_optimal)}",
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
        solve_result=solve_result,
    )


def solve_dataset(
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    results_dir: str | Path = DEFAULT_CPLEX_RESULTS_DIR,
    clear_existing: bool = True,
) -> DataSetSolveResult:
    """Resolve the stored dataset and write one cplex-style text file per instance."""

    input_dir = Path(data_dir)
    output_dir = Path(results_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if clear_existing:
        _clear_matching_files(output_dir, "galaxy_*.txt")
        summary_path = output_dir / "summary.json"
        if summary_path.exists():
            summary_path.unlink()

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
            average_solve_time_by_difficulty=MappingProxyType({}),
            average_solve_time_by_difficulty_and_size=MappingProxyType({}),
        )

    records: list[InstanceSolveResult] = []
    times_by_difficulty: dict[str, list[float]] = {}
    times_by_difficulty_and_size: dict[str, dict[str, list[float]]] = {}

    for instance_path in instance_paths:
        instance = load_instance(instance_path)
        record = solve_instance(
            instance,
            instance_path=instance_path,
            results_dir=output_dir,
        )
        records.append(record)
        times_by_difficulty.setdefault(record.requested_difficulty, []).append(
            record.solve_time
        )
        size_label = _grid_label(record.grid_size)
        times_by_difficulty_and_size.setdefault(
            record.requested_difficulty,
            {},
        ).setdefault(size_label, []).append(record.solve_time)

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

    summary_path = output_dir / "summary.json"
    summary_payload = {
        "instance_count": len(records),
        "average_solve_time_by_difficulty": dict(average_solve_time_by_difficulty),
        "average_solve_time_by_difficulty_and_size": {
            difficulty: dict(size_map)
            for difficulty, size_map in average_solve_time_by_difficulty_and_size.items()
        },
        "result_files": [record.result_path.name for record in records],
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
        average_solve_time_by_difficulty=average_solve_time_by_difficulty,
        average_solve_time_by_difficulty_and_size=average_solve_time_by_difficulty_and_size,
    )


__all__ = [
    "DEFAULT_CPLEX_RESULTS_DIR",
    "DEFAULT_DATA_DIR",
    "DEFAULT_GENERATION_RETRIES",
    "DEFAULT_GENERATION_SEED_SWEEP",
    "DEFAULT_INSTANCE_SEED_BLOCKS",
    "DataSetGenerationResult",
    "DataSetSolveResult",
    "InstanceGenerationResult",
    "InstanceSolveResult",
    "StoredPuzzleInstance",
    "generate_dataset",
    "generate_instance",
    "load_instance",
    "save_instance",
    "solve_dataset",
    "solve_instance",
]
