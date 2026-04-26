"""Pygame interface layer for the Galaxy MVP."""

from .app import run_phase_a_app
from .puzzle_loader import FixedPuzzle, load_phase_a_puzzle

__all__ = ["FixedPuzzle", "load_phase_a_puzzle", "run_phase_a_app"]
