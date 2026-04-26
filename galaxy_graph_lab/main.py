"""Pygame entrypoint for the first playable Galaxy MVP phase."""

from __future__ import annotations

import sys
from pathlib import Path

import pygame


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from galaxy_graph_lab.ui.app import run_phase_b_app
else:
    from .ui.app import run_phase_b_app


def build_status_report() -> str:
    """Return a short environment and UI status report."""

    return "\n".join(
        [
            "Galaxy Graph Lab setup check",
            f"Python: {sys.version.split()[0]}",
            f"Pygame: {pygame.version.ver}",
            "Status: environment is ready.",
            "UI Phase: B (clickable board geometry)",
        ]
    )


def main() -> None:
    """Launch the Phase B Pygame window with one fixed puzzle."""

    run_phase_b_app()


if __name__ == "__main__":
    main()
