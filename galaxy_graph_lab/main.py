"""Pygame entrypoint for the current playable Galaxy MVP."""

from __future__ import annotations

import sys
from pathlib import Path

import pygame


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from galaxy_graph_lab.ui.app import run_phase_f_app
else:
    from .ui.app import run_phase_f_app


def build_status_report() -> str:
    """Return a short environment and UI status report."""

    return "\n".join(
        [
            "Galaxy Graph Lab setup check",
            f"Python: {sys.version.split()[0]}",
            f"Pygame: {pygame.version.ver}",
            "Status: environment is ready.",
            "UI Phase: start screen + board scene",
        ]
    )


def main() -> None:
    """Launch the Pygame MVP with the start screen and board scene."""

    run_phase_f_app()


if __name__ == "__main__":
    main()
