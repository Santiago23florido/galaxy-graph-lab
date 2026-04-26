from __future__ import annotations

from types import MappingProxyType

import pygame

from ..core import validate_assignment
from .debug_tools import (
    DebugOverlayState,
    comparison_by_cell,
    comparison_counts,
    component_index_by_cell,
)
from .game_state import EditablePuzzleState
from .puzzle_loader import load_phase_a_puzzle
from .renderer import DebugOverlayView, build_board_layout, draw_phase_a_scene, hit_test_board_geometry


def run_phase_f_app(max_frames: int | None = None) -> None:
    """Open the Phase F Pygame window with developer-oriented debug overlays."""

    pygame.init()

    try:
        puzzle = load_phase_a_puzzle()
        layout = build_board_layout(puzzle.puzzle_data)
        surface = pygame.display.set_mode((layout.window_width, layout.window_height))
        pygame.display.set_caption("Galaxy Graph Lab - Phase F")

        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 34)
        body_font = pygame.font.Font(None, 24)
        small_font = pygame.font.Font(None, 21)

        running = True
        frame_count = 0
        hovered_hit = None
        game_state = EditablePuzzleState.from_center_ids(
            tuple(center.id for center in puzzle.puzzle_data.centers)
        )
        debug_state = DebugOverlayState()
        validation_result = validate_assignment(
            puzzle.puzzle_data,
            game_state.candidate_assignment(),
        )

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    game_state.reset_assignments()
                    validation_result = validate_assignment(
                        puzzle.puzzle_data,
                        game_state.candidate_assignment(),
                    )
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_a:
                    debug_state.show_admissible_domain = not debug_state.show_admissible_domain
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_k:
                    debug_state.show_kernel_cells = not debug_state.show_kernel_cells
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                    debug_state.show_components = not debug_state.show_components
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_s:
                    debug_state.ensure_exact_flow_result(puzzle.puzzle_data)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_l:
                    exact_result = debug_state.ensure_exact_flow_result(puzzle.puzzle_data)
                    if exact_result.assignment is not None:
                        game_state.load_solver_assignment(exact_result.assignment)
                        validation_result = validate_assignment(
                            puzzle.puzzle_data,
                            game_state.candidate_assignment(),
                        )
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                    exact_result = debug_state.ensure_exact_flow_result(puzzle.puzzle_data)
                    if exact_result.assignment is not None:
                        debug_state.show_solver_comparison = (
                            not debug_state.show_solver_comparison
                        )
                elif event.type == pygame.MOUSEMOTION:
                    hovered_hit = hit_test_board_geometry(
                        puzzle.puzzle_data,
                        layout,
                        event.pos,
                    )
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    clicked_hit = hit_test_board_geometry(
                        puzzle.puzzle_data,
                        layout,
                        event.pos,
                    )
                    game_state.apply_left_click(clicked_hit)
                    validation_result = validate_assignment(
                        puzzle.puzzle_data,
                        game_state.candidate_assignment(),
                    )

            candidate_assignment = game_state.candidate_assignment()
            selected_center_id = game_state.selected_center_id
            admissible_cells: tuple = ()
            if debug_state.show_admissible_domain and selected_center_id is not None:
                admissible_cells = puzzle.puzzle_data.admissible_cells_by_center[selected_center_id]

            kernel_cells_by_center = MappingProxyType({})
            if debug_state.show_kernel_cells:
                kernel_cells_by_center = puzzle.puzzle_data.kernel_by_center

            component_lookup = MappingProxyType({})
            if debug_state.show_components and selected_center_id is not None:
                component_lookup = component_index_by_cell(
                    puzzle.puzzle_data,
                    candidate_assignment[selected_center_id],
                )

            solver_result = debug_state.exact_flow_result
            solver_cached = solver_result is not None
            solver_success = bool(solver_result.success) if solver_result is not None else False
            solver_status_label = "Exact flow not loaded."
            if solver_result is not None and solver_result.success:
                solver_status_label = "Exact flow cached and feasible."
            elif solver_result is not None:
                solver_status_label = f"Exact flow unavailable: {solver_result.status}"

            comparison_lookup = MappingProxyType({})
            comparison_match_count = None
            comparison_mismatch_count = None
            exact_assignment_by_cell = debug_state.exact_assignment_by_cell()
            if debug_state.show_solver_comparison and exact_assignment_by_cell is not None:
                comparison_lookup = comparison_by_cell(
                    game_state.assigned_center_by_cell,
                    exact_assignment_by_cell,
                )
                (
                    comparison_match_count,
                    comparison_mismatch_count,
                ) = comparison_counts(comparison_lookup)

            debug_view = DebugOverlayView(
                show_admissible_domain=debug_state.show_admissible_domain,
                show_kernel_cells=debug_state.show_kernel_cells,
                show_components=debug_state.show_components,
                show_solver_comparison=debug_state.show_solver_comparison,
                admissible_center_id=selected_center_id if admissible_cells else None,
                admissible_cells=tuple(admissible_cells),
                kernel_cells_by_center=kernel_cells_by_center,
                component_index_by_cell=component_lookup,
                solver_cached=solver_cached,
                solver_success=solver_success,
                solver_status_label=solver_status_label,
                comparison_by_cell=comparison_lookup,
                comparison_match_count=comparison_match_count,
                comparison_mismatch_count=comparison_mismatch_count,
            )

            draw_phase_a_scene(
                surface,
                puzzle,
                layout,
                assigned_center_by_cell=game_state.assigned_center_by_cell,
                hovered_hit=hovered_hit,
                last_hit=game_state.last_hit,
                selected_center_id=selected_center_id,
                validation_result=validation_result,
                debug_view=debug_view,
                title_font=title_font,
                body_font=body_font,
                small_font=small_font,
            )
            pygame.display.flip()
            clock.tick(60)

            frame_count += 1
            if max_frames is not None and frame_count >= max_frames:
                running = False
    finally:
        pygame.quit()


def run_phase_d_app(max_frames: int | None = None) -> None:
    """Compatibility wrapper for the previous Phase D entrypoint name."""

    run_phase_f_app(max_frames=max_frames)


def run_phase_b_app(max_frames: int | None = None) -> None:
    """Compatibility wrapper for the previous Phase B entrypoint name."""

    run_phase_f_app(max_frames=max_frames)


def run_phase_c_app(max_frames: int | None = None) -> None:
    """Compatibility wrapper for the previous Phase C entrypoint name."""

    run_phase_f_app(max_frames=max_frames)


def run_phase_a_app(max_frames: int | None = None) -> None:
    """Compatibility wrapper for the previous Phase A entrypoint name."""

    run_phase_f_app(max_frames=max_frames)
