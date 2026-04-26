"""Pygame entrypoint for the first playable Galaxy MVP phase."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from galaxy_graph_lab.ui.app import run_phase_a_app
else:
    from .ui.app import run_phase_a_app


def main() -> None:
    """Launch the Phase A Pygame window with one fixed puzzle."""

    run_phase_a_app()


if __name__ == "__main__":
    main()
