"""Pygame interface layer for the Galaxy MVP."""

from .app import run_phase_a_app, run_phase_b_app, run_phase_c_app, run_phase_d_app, run_phase_f_app
from .debug_tools import DebugOverlayState
from .game_state import EditablePuzzleState
from .puzzle_loader import FixedPuzzle, load_phase_a_puzzle
from .renderer import DebugOverlayView, GeometryHit, cell_at_pixel, center_at_pixel, hit_test_board_geometry
from .solver_session import SolverSessionState
from .start_screen import (
    StartScreenHit,
    StartScreenLayout,
    StartScreenState,
    apply_start_screen_hit,
    build_generation_request_from_state,
    build_start_screen_layout,
    default_start_screen_state,
    difficulty_button_rects,
    draw_start_screen,
    generate_puzzle_button_rect,
    grid_size_button_rects,
    hit_test_start_screen,
)

__all__ = [
    "DebugOverlayState",
    "DebugOverlayView",
    "EditablePuzzleState",
    "FixedPuzzle",
    "GeometryHit",
    "SolverSessionState",
    "StartScreenHit",
    "StartScreenLayout",
    "StartScreenState",
    "apply_start_screen_hit",
    "build_generation_request_from_state",
    "build_start_screen_layout",
    "cell_at_pixel",
    "center_at_pixel",
    "default_start_screen_state",
    "difficulty_button_rects",
    "draw_start_screen",
    "generate_puzzle_button_rect",
    "grid_size_button_rects",
    "hit_test_board_geometry",
    "hit_test_start_screen",
    "load_phase_a_puzzle",
    "run_phase_a_app",
    "run_phase_b_app",
    "run_phase_c_app",
    "run_phase_d_app",
    "run_phase_f_app",
]
