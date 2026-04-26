"""Pygame interface layer for the Galaxy MVP."""

from .app import run_phase_a_app, run_phase_b_app, run_phase_c_app
from .game_state import EditablePuzzleState
from .puzzle_loader import FixedPuzzle, load_phase_a_puzzle
from .renderer import GeometryHit, cell_at_pixel, center_at_pixel, hit_test_board_geometry

__all__ = [
    "EditablePuzzleState",
    "FixedPuzzle",
    "GeometryHit",
    "cell_at_pixel",
    "center_at_pixel",
    "hit_test_board_geometry",
    "load_phase_a_puzzle",
    "run_phase_a_app",
    "run_phase_b_app",
    "run_phase_c_app",
]
