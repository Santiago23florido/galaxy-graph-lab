from __future__ import annotations

import argparse
import re
from pathlib import Path

from .core import (
    BoardSpec,
    DATASET_SOLVE_BACKEND_BOTH,
    DEFAULT_CPLEX_RESULTS_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_FIXED_DATASET_END_SIDE,
    DEFAULT_FIXED_DATASET_START_SIDE,
    DEFAULT_DATASET_INSTANCES_PER_SIZE,
    DEFAULT_DATASET_SELECTION_MIN_SOLVE_TIME_SECONDS,
    DEFAULT_SOLVER_BACKEND,
    DEFAULT_INSTANCE_SEED_BLOCKS,
    DEFAULT_GENERATION_RETRIES,
    DEFAULT_GENERATION_SEED_SWEEP,
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_HARD,
    GENERATION_DIFFICULTY_MEDIUM,
    SUPPORTED_SOLVER_BACKENDS,
    find_hard_threshold_limit,
    generate_dataset,
    solve_dataset,
)


def _counts_from_args(args: argparse.Namespace) -> dict[str, int]:
    return {
        GENERATION_DIFFICULTY_EASY: args.easy_count,
        GENERATION_DIFFICULTY_MEDIUM: args.medium_count,
        GENERATION_DIFFICULTY_HARD: args.hard_count,
    }


def _fixed_dimensions(start_side: int, end_side: int) -> dict[str, tuple[BoardSpec, ...]]:
    if start_side <= 0:
        raise ValueError("start_side must be positive.")
    if end_side < start_side:
        raise ValueError("end_side must be at least start_side.")

    dimensions = tuple(
        BoardSpec(rows=side, cols=side)
        for side in range(start_side, end_side + 1)
    )
    return {
        GENERATION_DIFFICULTY_EASY: dimensions,
        GENERATION_DIFFICULTY_MEDIUM: dimensions,
        GENERATION_DIFFICULTY_HARD: dimensions,
    }


def _print_progress(message: str) -> None:
    print(message, flush=True)


_GENERATED_INSTANCE_PROGRESS_PATTERN = re.compile(
    r"^Generated (?P<difficulty>\w+) (?P<size>\d+x\d+) instance \d+ .* solved it in "
    r"(?P<solve_time>\d+(?:\.\d+)?)s\.$"
)
_REFERENCE_FOUND_PROGRESS_PATTERN = re.compile(
    r"^Reference dimension found for (?P<difficulty>\w+): (?P<size>\d+x\d+) "
    r"solved in (?P<solve_time>\d+(?:\.\d+)?)s\.$"
)
_DEBUG_TIMING_PATTERN = re.compile(
    r".*(?:generación|solver|continuando|below threshold|Searching reference dimension|Reference dimension found|Using hard reference threshold|stage=|seed_attempt=|generation_attempt=).*"
)


def _print_generation_progress(message: str) -> None:
    match = _GENERATED_INSTANCE_PROGRESS_PATTERN.match(message)
    if match is None:
        match = _REFERENCE_FOUND_PROGRESS_PATTERN.match(message)
    if match is None:
        # Imprimir mensajes de debug de timing
        if _DEBUG_TIMING_PATTERN.match(message):
            print(message, flush=True)
        return

    difficulty = match.group("difficulty")
    size_label = match.group("size")
    solve_time = match.group("solve_time")
    print(
        f"nivel={difficulty} talla={size_label} tiempo={solve_time}s",
        flush=True,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m galaxy_graph_lab.dataset_cli",
        description="Dataset generation and batch solving tools for Galaxy Graph Lab.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(
        "generate-dataset",
        help=(
            "Generate a fixed dataset over square sizes from 7x7 to 11x11 "
            "without running the hard-threshold search first."
        ),
    )
    generate_parser.add_argument(
        "--easy-count",
        type=int,
        default=DEFAULT_DATASET_INSTANCES_PER_SIZE,
        help="Instances to generate for each easy grid size.",
    )
    generate_parser.add_argument(
        "--medium-count",
        type=int,
        default=DEFAULT_DATASET_INSTANCES_PER_SIZE,
        help="Instances to generate for each medium grid size.",
    )
    generate_parser.add_argument(
        "--hard-count",
        type=int,
        default=DEFAULT_DATASET_INSTANCES_PER_SIZE,
        help="Instances to generate for each hard grid size.",
    )
    generate_parser.add_argument(
        "--start-side",
        type=int,
        default=DEFAULT_FIXED_DATASET_START_SIDE,
        help="Minimum square side included in the fixed dataset generation range.",
    )
    generate_parser.add_argument(
        "--end-side",
        type=int,
        default=DEFAULT_FIXED_DATASET_END_SIDE,
        help="Maximum square side included in the fixed dataset generation range.",
    )
    generate_parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory where generated instances will be stored.",
    )
    generate_parser.add_argument(
        "--max-generation-retries",
        type=int,
        default=DEFAULT_GENERATION_RETRIES,
        help="Internal retry budget used by the puzzle generator.",
    )
    generate_parser.add_argument(
        "--seed-sweep",
        type=int,
        default=DEFAULT_GENERATION_SEED_SWEEP,
        help="How many outer seed shifts to try per requested instance.",
    )
    generate_parser.add_argument(
        "--base-seed",
        type=int,
        default=None,
        help="Optional deterministic base seed for dataset generation.",
    )
    generate_parser.add_argument(
        "--seed-block-count",
        type=int,
        default=DEFAULT_INSTANCE_SEED_BLOCKS,
        help="How many outer seed blocks to try per requested instance.",
    )
    generate_parser.add_argument(
        "--solver-backend",
        default=DEFAULT_SOLVER_BACKEND,
        choices=sorted(SUPPORTED_SOLVER_BACKENDS),
        help="Solver backend to use for dataset generation.",
    )

    threshold_parser = subparsers.add_parser(
        "find-hard-threshold",
        help=(
            "Search the largest hard square size whose solve time remains under "
            "the selected threshold."
        ),
    )
    threshold_parser.add_argument(
        "--threshold-seconds",
        type=float,
        default=DEFAULT_DATASET_SELECTION_MIN_SOLVE_TIME_SECONDS,
        help="Solve-time threshold used to stop the hard-size search.",
    )
    threshold_parser.add_argument(
        "--start-side",
        type=int,
        default=DEFAULT_FIXED_DATASET_START_SIDE,
        help="First square side tested in the hard-threshold search.",
    )
    threshold_parser.add_argument(
        "--max-side",
        type=int,
        default=31,
        help="Maximum square side tested in the hard-threshold search.",
    )
    threshold_parser.add_argument(
        "--max-generation-retries",
        type=int,
        default=DEFAULT_GENERATION_RETRIES,
        help="Internal retry budget used by the puzzle generator.",
    )
    threshold_parser.add_argument(
        "--seed-sweep",
        type=int,
        default=DEFAULT_GENERATION_SEED_SWEEP,
        help="How many outer seed shifts to try for each tested size.",
    )
    threshold_parser.add_argument(
        "--base-seed",
        type=int,
        default=None,
        help="Optional deterministic base seed for threshold search.",
    )
    threshold_parser.add_argument(
        "--seed-block-count",
        type=int,
        default=DEFAULT_INSTANCE_SEED_BLOCKS,
        help="How many outer seed blocks to try for each tested size.",
    )
    threshold_parser.add_argument(
        "--solver-backend",
        default=DEFAULT_SOLVER_BACKEND,
        choices=sorted(SUPPORTED_SOLVER_BACKENDS),
        help="Solver backend to use for the hard-threshold search.",
    )

    solve_parser = subparsers.add_parser(
        "solve-dataset",
        help="Solve every stored instance and write cplex-style result files.",
    )
    solve_parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing stored instance JSON files.",
    )
    solve_parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_CPLEX_RESULTS_DIR,
        help="Directory where cplex-style result files will be written.",
    )
    solve_parser.add_argument(
        "--solver-backend",
        default=DEFAULT_SOLVER_BACKEND,
        choices=(
            tuple(sorted(SUPPORTED_SOLVER_BACKENDS))
            + (DATASET_SOLVE_BACKEND_BOTH,)
        ),
        help=(
            "Solve with one backend or run both backends over every stored instance."
        ),
    )

    return parser


def main() -> None:
    """Run the dataset generation or dataset solving command-line tool."""

    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "generate-dataset":
        print("generando dataset fijo...", flush=True)
        result = generate_dataset(
            _counts_from_args(args),
            data_dir=args.data_dir,
            max_generation_retries=args.max_generation_retries,
            seed_sweep=args.seed_sweep,
            seed_block_count=args.seed_block_count,
            base_seed=args.base_seed,
            dimensions_by_difficulty=_fixed_dimensions(args.start_side, args.end_side),
            selection_solver_backend=args.solver_backend,
            dataset_instance_min_solve_time_seconds=0.0,
            progress_callback=_print_generation_progress,
        )
        if not result.success:
            raise SystemExit(result.message)

        print(result.message)
        print(f"dataDir={result.data_dir}")
        print(f"manifest={result.manifest_path}")
        for difficulty, count in result.instances_by_difficulty.items():
            print(f"{difficulty}Count={count}")
        return

    if args.command == "find-hard-threshold":
        print("buscando limite hard...", flush=True)
        result = find_hard_threshold_limit(
            threshold_seconds=args.threshold_seconds,
            solver_backend=args.solver_backend,
            start_side=args.start_side,
            max_side=args.max_side,
            max_generation_retries=args.max_generation_retries,
            seed_sweep=args.seed_sweep,
            seed_block_count=args.seed_block_count,
            base_seed=args.base_seed,
            progress_callback=_print_generation_progress,
        )
        if not result.success:
            raise SystemExit(result.message)

        print(result.message)
        print(f"thresholdSeconds={result.threshold_seconds:.6f}")
        print(f"solverBackend={result.solver_backend}")
        if result.max_solved_grid_size is not None:
            print(
                "maxSolvedGrid="
                f"{result.max_solved_grid_size.rows}x{result.max_solved_grid_size.cols}"
            )
            print(f"maxSolvedSolveTime={result.max_solved_solve_time:.6f}")
        if result.first_exceeding_grid_size is not None:
            print(
                "firstExceedingGrid="
                f"{result.first_exceeding_grid_size.rows}x{result.first_exceeding_grid_size.cols}"
            )
            print(f"firstExceedingSolveTime={result.first_exceeding_solve_time:.6f}")
        return

    if args.command == "solve-dataset":
        result = solve_dataset(
            data_dir=args.data_dir,
            results_dir=args.results_dir,
            solver_backend=args.solver_backend,
        )
        if not result.success:
            raise SystemExit(result.message)

        print(result.message)
        print(f"resultsDir={result.results_dir}")
        print(f"summary={result.summary_path}")
        print(f"solverBackends={','.join(result.solver_backends)}")
        for backend_name, average_time in result.average_solve_time_by_backend.items():
            print(f"{backend_name}AverageSolveTime={average_time:.6f}")
        for difficulty, average_time in result.average_solve_time_by_difficulty.items():
            print(f"{difficulty}AverageSolveTime={average_time:.6f}")
        for backend_name, difficulty_map in result.average_solve_time_by_backend_and_difficulty.items():
            for difficulty, average_time in difficulty_map.items():
                print(f"{backend_name}.{difficulty}AverageSolveTime={average_time:.6f}")
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
