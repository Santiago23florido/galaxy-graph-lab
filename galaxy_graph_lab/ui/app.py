from __future__ import annotations

from types import MappingProxyType

import pygame

from ..core import generate_puzzle, validate_assignment
from .debug_tools import (
    DebugOverlayState,
    comparison_by_cell,
    comparison_counts,
    component_index_by_cell,
)
from .game_state import EditablePuzzleState
from .puzzle_loader import FixedPuzzle
from .renderer import (
    DebugOverlayView,
    build_board_layout,
    draw_phase_a_scene,
    hit_test_board_geometry,
    restore_manual_button_rect,
    show_solution_button_rect,
)
from .solver_session import SolverSessionState
from .start_screen import (
    StartScreenState,
    apply_start_screen_hit,
    build_generation_request_from_state,
    build_start_screen_layout,
    default_start_screen_state,
    draw_start_screen,
    hit_test_start_screen,
)


def request_solution_for_current_board(
    puzzle_data,
    game_state: EditablePuzzleState,
    solver_session: SolverSessionState,
) -> bool:
    """Request one solver solution guided by the current player assignment."""

    previous_assignment = dict(game_state.assigned_center_by_cell)
    result = solver_session.request_solution(
        puzzle_data,
        preferred_assignment_by_cell=previous_assignment,
    )
    if not result.success or result.assignment is None:
        return False

    solver_session.capture_manual_snapshot(previous_assignment)
    game_state.load_solver_assignment(result.assignment)
    solver_session.mark_solution_loaded()
    return True


def restore_manual_board_state(
    game_state: EditablePuzzleState,
    solver_session: SolverSessionState,
) -> bool:
    """Restore the last saved manual snapshot into the editable board."""

    restored_assignment = solver_session.restore_manual_snapshot()
    if restored_assignment is None:
        return False

    game_state.replace_assignments(restored_assignment)
    game_state.last_hit = None
    return True


def build_generated_ui_puzzle(
    start_screen_state: StartScreenState,
) -> tuple[FixedPuzzle | None, str]:
    """Generate one UI puzzle from the current start-screen selection."""

    generation_request = build_generation_request_from_state(start_screen_state)
    generation_result = generate_puzzle(generation_request)
    if not generation_result.success or generation_result.puzzle is None:
        return None, generation_result.message

    return (
        FixedPuzzle(
            name=generation_result.puzzle.name,
            puzzle_data=generation_result.puzzle.puzzle_data,
        ),
        generation_result.message,
    )


def run_phase_f_app(max_frames: int | None = None) -> None:
    """Open the Pygame MVP with a start screen and the current board scene."""

    pygame.init()

    try:
        start_screen_layout = build_start_screen_layout()
        surface = pygame.display.set_mode(
            (start_screen_layout.window_width, start_screen_layout.window_height)
        )
        pygame.display.set_caption("Galaxy Graph Lab")

        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 34)
        body_font = pygame.font.Font(None, 24)
        small_font = pygame.font.Font(None, 21)

        running = True
        scene = "start"
        frame_count = 0
        start_screen_state = default_start_screen_state()
        hovered_start_hit = None

        puzzle: FixedPuzzle | None = None
        layout = None
        hovered_hit = None
        hovered_show_solution_button = False
        hovered_restore_manual_button = False
        game_state: EditablePuzzleState | None = None
        debug_state: DebugOverlayState | None = None
        solver_session: SolverSessionState | None = None
        validation_result = None

        def load_board_scene(next_puzzle: FixedPuzzle) -> None:
            nonlocal puzzle
            nonlocal layout
            nonlocal surface
            nonlocal scene
            nonlocal hovered_hit
            nonlocal hovered_show_solution_button
            nonlocal hovered_restore_manual_button
            nonlocal game_state
            nonlocal debug_state
            nonlocal solver_session
            nonlocal validation_result

            puzzle = next_puzzle
            layout = build_board_layout(puzzle.puzzle_data)
            surface = pygame.display.set_mode((layout.window_width, layout.window_height))
            game_state = EditablePuzzleState.from_center_ids(
                tuple(center.id for center in puzzle.puzzle_data.centers)
            )
            debug_state = DebugOverlayState()
            solver_session = SolverSessionState()
            validation_result = validate_assignment(
                puzzle.puzzle_data,
                game_state.candidate_assignment(),
            )
            hovered_hit = None
            hovered_show_solution_button = False
            hovered_restore_manual_button = False
            scene = "board"

        def refresh_validation() -> None:
            nonlocal validation_result
            assert puzzle is not None
            assert game_state is not None
            validation_result = validate_assignment(
                puzzle.puzzle_data,
                game_state.candidate_assignment(),
            )

        def request_and_show_solution() -> None:
            assert puzzle is not None
            assert game_state is not None
            assert solver_session is not None
            if request_solution_for_current_board(
                puzzle.puzzle_data,
                game_state,
                solver_session,
            ):
                refresh_validation()

        def restore_manual_snapshot() -> None:
            assert game_state is not None
            assert solver_session is not None
            if restore_manual_board_state(game_state, solver_session):
                refresh_validation()

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif scene == "start":
                    if event.type == pygame.MOUSEMOTION:
                        hovered_start_hit = hit_test_start_screen(
                            start_screen_layout,
                            start_screen_state,
                            event.pos,
                        )
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        clicked_hit = hit_test_start_screen(
                            start_screen_layout,
                            start_screen_state,
                            event.pos,
                        )
                        if clicked_hit is not None and clicked_hit.kind == "generate":
                            next_puzzle, message = build_generated_ui_puzzle(start_screen_state)
                            start_screen_state.status_message = message
                            if next_puzzle is not None:
                                load_board_scene(next_puzzle)
                        else:
                            apply_start_screen_hit(start_screen_state, clicked_hit)
                elif scene == "board":
                    assert puzzle is not None
                    assert layout is not None
                    assert game_state is not None
                    assert debug_state is not None
                    assert solver_session is not None
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                        game_state.reset_assignments()
                        solver_session.mark_player_controlled()
                        solver_session.discard_manual_snapshot()
                        refresh_validation()
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_h:
                        restore_manual_snapshot()
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_a:
                        debug_state.show_admissible_domain = not debug_state.show_admissible_domain
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_k:
                        debug_state.show_kernel_cells = not debug_state.show_kernel_cells
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                        debug_state.show_components = not debug_state.show_components
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_s:
                        request_and_show_solution()
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                        if solver_session.solver_assignment_by_cell() is not None:
                            debug_state.show_solver_comparison = (
                                not debug_state.show_solver_comparison
                            )
                    elif event.type == pygame.MOUSEMOTION:
                        hovered_show_solution_button = show_solution_button_rect(
                            layout,
                            title_font,
                            body_font,
                            small_font,
                        ).collidepoint(event.pos)
                        hovered_restore_manual_button = restore_manual_button_rect(
                            layout,
                            title_font,
                            body_font,
                            small_font,
                        ).collidepoint(event.pos)
                        hovered_hit = hit_test_board_geometry(
                            puzzle.puzzle_data,
                            layout,
                            event.pos,
                        )
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if show_solution_button_rect(
                            layout,
                            title_font,
                            body_font,
                            small_font,
                        ).collidepoint(event.pos):
                            request_and_show_solution()
                            continue
                        if restore_manual_button_rect(
                            layout,
                            title_font,
                            body_font,
                            small_font,
                        ).collidepoint(event.pos):
                            restore_manual_snapshot()
                            continue

                        previous_assignment = dict(game_state.assigned_center_by_cell)
                        clicked_hit = hit_test_board_geometry(
                            puzzle.puzzle_data,
                            layout,
                            event.pos,
                        )
                        game_state.apply_left_click(clicked_hit)
                        if dict(game_state.assigned_center_by_cell) != previous_assignment:
                            solver_session.mark_manual_edit()
                        refresh_validation()

            if scene == "start":
                draw_start_screen(
                    surface,
                    start_screen_layout,
                    start_screen_state,
                    hovered_start_hit,
                    title_font,
                    body_font,
                    small_font,
                )
            elif scene == "board":
                assert puzzle is not None
                assert layout is not None
                assert game_state is not None
                assert debug_state is not None
                assert solver_session is not None
                assert validation_result is not None

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

                solver_result = solver_session.solver_result
                solver_cached = solver_session.solver_result_cached
                solver_success = bool(solver_result.success) if solver_result is not None else False

                comparison_lookup = MappingProxyType({})
                comparison_match_count = None
                comparison_mismatch_count = None
                exact_assignment_by_cell = solver_session.solver_assignment_by_cell()
                if debug_state.show_solver_comparison and exact_assignment_by_cell is not None:
                    comparison_reference = solver_session.comparison_reference_assignment_by_cell(
                        game_state.assigned_center_by_cell,
                    )
                    comparison_lookup = comparison_by_cell(
                        comparison_reference,
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
                    solver_result_requested=solver_session.solver_result_requested,
                    solver_cached=solver_cached,
                    solver_success=solver_success,
                    solver_status_label=solver_session.solver_status_label,
                    solver_message=solver_session.solver_message,
                    solution_visible=solver_session.solution_visible,
                    solution_loaded_into_board=solver_session.solution_loaded_into_board,
                    board_mode_label=solver_session.board_mode_label,
                    show_solution_button_hovered=hovered_show_solution_button,
                    restore_manual_button_hovered=hovered_restore_manual_button,
                    can_restore_manual_snapshot=solver_session.can_restore_manual_snapshot,
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
