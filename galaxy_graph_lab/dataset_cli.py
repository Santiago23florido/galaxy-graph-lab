from __future__ import annotations

import argparse
from pathlib import Path

from .core import (
    DATASET_SOLVE_BACKEND_BOTH,
    DEFAULT_CPLEX_RESULTS_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_SOLVER_BACKEND,
    DEFAULT_INSTANCE_SEED_BLOCKS,
    DEFAULT_GENERATION_RETRIES,
    DEFAULT_GENERATION_SEED_SWEEP,
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_HARD,
    GENERATION_DIFFICULTY_MEDIUM,
    SUPPORTED_SOLVER_BACKENDS,
    generate_dataset,
    solve_dataset,
)


def _counts_from_args(args: argparse.Namespace) -> dict[str, int]:
    return {
        GENERATION_DIFFICULTY_EASY: args.easy_count,
        GENERATION_DIFFICULTY_MEDIUM: args.medium_count,
        GENERATION_DIFFICULTY_HARD: args.hard_count,
    }


def _print_progress(message: str) -> None:
    print(message, flush=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m galaxy_graph_lab.dataset_cli",
        description="Dataset generation and batch solving tools for Galaxy Graph Lab.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(
        "generate-dataset",
        help="Generate a dataset that covers every allowed grid size per difficulty.",
    )
    generate_parser.add_argument(
        "--easy-count",
        type=int,
        default=1,
        help="Instances to generate for each easy grid size.",
    )
    generate_parser.add_argument(
        "--medium-count",
        type=int,
        default=1,
        help="Instances to generate for each medium grid size.",
    )
    generate_parser.add_argument(
        "--hard-count",
        type=int,
        default=1,
        help="Instances to generate for each hard grid size.",
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
        result = generate_dataset(
            _counts_from_args(args),
            data_dir=args.data_dir,
            max_generation_retries=args.max_generation_retries,
            seed_sweep=args.seed_sweep,
            seed_block_count=args.seed_block_count,
            base_seed=args.base_seed,
            progress_callback=_print_progress,
        )
        if not result.success:
            raise SystemExit(result.message)

        print(result.message)
        print(f"dataDir={result.data_dir}")
        print(f"manifest={result.manifest_path}")
        for difficulty, count in result.instances_by_difficulty.items():
            print(f"{difficulty}Count={count}")
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
