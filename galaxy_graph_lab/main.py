"""Pygame entrypoint for the current playable Galaxy MVP."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pygame


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from galaxy_graph_lab.core import DEFAULT_SOLVER_BACKEND, SUPPORTED_SOLVER_BACKENDS
    from galaxy_graph_lab.ui.app import run_phase_f_app
else:
    from .core import DEFAULT_SOLVER_BACKEND, SUPPORTED_SOLVER_BACKENDS
    from .ui.app import run_phase_f_app


def build_status_report() -> str:
    """Return a short environment and UI status report."""

    return "\n".join(
        [
            "Galaxy Graph Lab setup check",
            f"Python: {sys.version.split()[0]}",
            f"Pygame: {pygame.version.ver}",
            "Status: environment is ready.",
            "UI Phase: home screen + selector + board scene",
        ]
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m galaxy_graph_lab.main",
        description="Launch the Galaxy Graph Lab playable UI.",
    )
    parser.add_argument(
        "--solver-backend",
        default=DEFAULT_SOLVER_BACKEND,
        choices=tuple(sorted(SUPPORTED_SOLVER_BACKENDS)),
        help="Select the backend used when the game requests a solver solution.",
    )
    return parser


def main() -> None:
    """Launch the Pygame MVP with the start screen and board scene."""

    args = _build_parser().parse_args()
    run_phase_f_app(solver_backend=args.solver_backend)


if __name__ == "__main__":
    main()
