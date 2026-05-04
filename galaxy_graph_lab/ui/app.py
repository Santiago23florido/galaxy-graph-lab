from __future__ import annotations

import secrets
from types import MappingProxyType

import pygame

from ..core import DEFAULT_SOLVER_BACKEND, generate_puzzle, validate_assignment
from .debug_tools import (
    DebugOverlayState,
    comparison_by_cell,
    comparison_counts,
    component_index_by_cell,
)
from .game_state import EditablePuzzleState
from .home_screen import (
    apply_home_screen_hit,
    build_home_screen_layout,
    default_home_screen_state,
    draw_detail_screen,
    draw_home_screen,
    hit_test_detail_screen,
    hit_test_home_screen,
)
from .puzzle_loader import FixedPuzzle
from .renderer import (
    DebugOverlayView,
    build_board_layout,
    draw_phase_a_scene,
    hit_test_board_geometry,
    info_panel_rect,
    menu_button_rect,
    restore_manual_button_rect,
    return_home_button_rect,
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

_UI_GENERATION_RETRIES_PER_SEED = 64
_UI_GENERATION_SEED_SWEEP = 24
_WINDOW_FLAGS = pygame.RESIZABLE
_WINDOW_RESIZED_EVENT = getattr(pygame, "WINDOWRESIZED", None)


def _random_generation_base_seed() -> int:
    """Return one fresh base seed for a new UI generation request."""

    return secrets.randbelow(2**31)


def _window_size_from_event(
    event: pygame.event.Event,
    surface: pygame.Surface,
) -> tuple[int, int]:
    """Return one resize target from any supported Pygame resize event."""

    event_size = getattr(event, "size", None)
    if isinstance(event_size, tuple) and len(event_size) == 2:
        return int(event_size[0]), int(event_size[1])

    for width_name, height_name in (("w", "h"), ("x", "y")):
        width = getattr(event, width_name, None)
        height = getattr(event, height_name, None)
        if isinstance(width, int | float) and isinstance(height, int | float):
            return int(width), int(height)

    display_surface = pygame.display.get_surface()
    if display_surface is not None:
        return display_surface.get_size()

    return surface.get_size()


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
    *,
    base_seed: int | None = None,
) -> tuple[FixedPuzzle | None, str]:
    """Generate one UI puzzle from the current start-screen selection."""

    if base_seed is None:
        base_seed = _random_generation_base_seed()

    for seed_offset in range(_UI_GENERATION_SEED_SWEEP):
        generation_request = build_generation_request_from_state(
            start_screen_state,
            random_seed=base_seed + seed_offset,
            max_generation_retries=_UI_GENERATION_RETRIES_PER_SEED,
        )
        generation_result = generate_puzzle(generation_request)
        if not generation_result.success or generation_result.puzzle is None:
            continue

        return (
            FixedPuzzle(
                name=generation_result.puzzle.name,
                puzzle_data=generation_result.puzzle.puzzle_data,
            ),
            generation_result.message,
        )

    return (
        None,
        (
            "Could not generate a certified puzzle for the selected "
            "difficulty and grid size after repeated attempts."
        ),
    )


def run_phase_f_app(
    max_frames: int | None = None,
    *,
    solver_backend: str = DEFAULT_SOLVER_BACKEND,
) -> None:
    """Open the Pygame MVP with a home screen, selector, and board scene."""

    pygame.init()

    try:
        home_screen_layout = build_home_screen_layout()
        start_screen_layout = build_start_screen_layout(
            (home_screen_layout.window_width, home_screen_layout.window_height)
        )
        surface = pygame.display.set_mode(
            (home_screen_layout.window_width, home_screen_layout.window_height),
            _WINDOW_FLAGS,
        )
        pygame.display.set_caption("Galaxy Graph Lab")

        clock = pygame.time.Clock()
        hero_font = pygame.font.Font(None, 58)
        title_font = pygame.font.Font(None, 34)
        body_font = pygame.font.Font(None, 24)
        small_font = pygame.font.Font(None, 21)

        running = True
        scene = "home"
        frame_count = 0
        home_screen_state = default_home_screen_state()
        hovered_home_hit = None
        hovered_detail_hit = None
        start_screen_state = default_start_screen_state()
        hovered_start_hit = None

        puzzle: FixedPuzzle | None = None
        layout = None
        hovered_hit = None
        hovered_show_solution_button = False
        hovered_restore_manual_button = False
        hovered_home_button = False
        hovered_menu_button = False
        info_menu_open = False
        game_state: EditablePuzzleState | None = None
        debug_state: DebugOverlayState | None = None
        solver_session: SolverSessionState | None = None
        validation_result = None

        def resize_window(target_size: tuple[int, int]) -> None:
            nonlocal home_screen_layout
            nonlocal start_screen_layout
            nonlocal layout
            nonlocal surface

            home_screen_layout = build_home_screen_layout(target_size)
            start_screen_layout = build_start_screen_layout(target_size)

            if scene == "board" and puzzle is not None:
                layout = build_board_layout(
                    puzzle.puzzle_data,
                    window_size=target_size,
                )
                surface = pygame.display.set_mode(
                    (layout.window_width, layout.window_height),
                    _WINDOW_FLAGS,
                )
                return

            if scene in {"home", "rules", "credits"}:
                surface = pygame.display.set_mode(
                    (home_screen_layout.window_width, home_screen_layout.window_height),
                    _WINDOW_FLAGS,
                )
                return

            surface = pygame.display.set_mode(
                (start_screen_layout.window_width, start_screen_layout.window_height),
                _WINDOW_FLAGS,
            )

        def load_board_scene(next_puzzle: FixedPuzzle) -> None:
            nonlocal puzzle
            nonlocal layout
            nonlocal surface
            nonlocal scene
            nonlocal hovered_hit
            nonlocal hovered_show_solution_button
            nonlocal hovered_restore_manual_button
            nonlocal hovered_home_button
            nonlocal hovered_menu_button
            nonlocal info_menu_open
            nonlocal game_state
            nonlocal debug_state
            nonlocal solver_session
            nonlocal validation_result

            puzzle = next_puzzle
            layout = build_board_layout(
                puzzle.puzzle_data,
                window_size=surface.get_size(),
            )
            surface = pygame.display.set_mode(
                (layout.window_width, layout.window_height),
                _WINDOW_FLAGS,
            )
            game_state = EditablePuzzleState.from_center_ids(
                tuple(center.id for center in puzzle.puzzle_data.centers)
            )
            debug_state = DebugOverlayState()
            solver_session = SolverSessionState(solver_backend=solver_backend)
            validation_result = validate_assignment(
                puzzle.puzzle_data,
                game_state.candidate_assignment(),
            )
            hovered_hit = None
            hovered_show_solution_button = False
            hovered_restore_manual_button = False
            hovered_home_button = False
            hovered_menu_button = False
            info_menu_open = False
            scene = "board"

        def load_selection_scene() -> None:
            nonlocal scene
            nonlocal hovered_start_hit

            scene = "start"
            resize_window(surface.get_size())
            hovered_start_hit = None

        def load_detail_scene(panel_kind: str) -> None:
            nonlocal scene
            nonlocal hovered_detail_hit

            if panel_kind not in {"rules", "credits"}:
                raise ValueError(f"Unknown detail scene: {panel_kind}")

            scene = panel_kind
            resize_window(surface.get_size())
            hovered_detail_hit = None

        def load_home_scene() -> None:
            nonlocal scene
            nonlocal hovered_home_hit
            nonlocal hovered_detail_hit
            nonlocal hovered_start_hit
            nonlocal hovered_hit
            nonlocal hovered_show_solution_button
            nonlocal hovered_restore_manual_button
            nonlocal hovered_home_button
            nonlocal hovered_menu_button
            nonlocal info_menu_open

            scene = "home"
            resize_window(surface.get_size())
            hovered_home_hit = None
            hovered_detail_hit = None
            hovered_start_hit = None
            hovered_hit = None
            hovered_show_solution_button = False
            hovered_restore_manual_button = False
            hovered_home_button = False
            hovered_menu_button = False
            info_menu_open = False

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
                elif event.type == pygame.VIDEORESIZE or event.type == _WINDOW_RESIZED_EVENT:
                    resize_window(_window_size_from_event(event, surface))
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif scene == "home":
                    if event.type == pygame.MOUSEMOTION:
                        hovered_home_hit = hit_test_home_screen(
                            home_screen_layout,
                            event.pos,
                        )
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        clicked_hit = hit_test_home_screen(
                            home_screen_layout,
                            event.pos,
                        )
                        if clicked_hit is not None and clicked_hit.kind == "start":
                            load_selection_scene()
                        else:
                            apply_home_screen_hit(home_screen_state, clicked_hit)
                            if clicked_hit is not None and clicked_hit.kind in {"rules", "credits"}:
                                load_detail_scene(clicked_hit.kind)
                elif scene in {"rules", "credits"}:
                    if event.type == pygame.MOUSEMOTION:
                        hovered_detail_hit = hit_test_detail_screen(
                            home_screen_layout,
                            event.pos,
                        )
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        clicked_hit = hit_test_detail_screen(
                            home_screen_layout,
                            event.pos,
                        )
                        if clicked_hit is not None and clicked_hit.kind == "start":
                            load_selection_scene()
                        elif clicked_hit is not None and clicked_hit.kind == "back":
                            hovered_home_hit = None
                            scene = "home"
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
                        hovered_home_button = return_home_button_rect(layout).collidepoint(event.pos)
                        hovered_menu_button = menu_button_rect(layout).collidepoint(event.pos)
                        if info_menu_open and info_panel_rect(layout).collidepoint(event.pos):
                            hovered_hit = None
                            continue
                        hovered_hit = hit_test_board_geometry(
                            puzzle.puzzle_data,
                            layout,
                            event.pos,
                        )
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if menu_button_rect(layout).collidepoint(event.pos):
                            info_menu_open = not info_menu_open
                            continue
                        if return_home_button_rect(layout).collidepoint(event.pos):
                            load_home_scene()
                            continue
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
                        if info_menu_open and info_panel_rect(layout).collidepoint(event.pos):
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

            if scene == "home":
                draw_home_screen(
                    surface,
                    home_screen_layout,
                    hovered_home_hit,
                    hero_font,
                    title_font,
                    body_font,
                    small_font,
                )
            elif scene in {"rules", "credits"}:
                draw_detail_screen(
                    surface,
                    home_screen_layout,
                    scene,
                    hovered_detail_hit,
                    hero_font,
                    title_font,
                    body_font,
                    small_font,
                )
            elif scene == "start":
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
                    home_button_hovered=hovered_home_button,
                    menu_button_hovered=hovered_menu_button,
                    info_menu_open=info_menu_open,
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


def run_phase_d_app(
    max_frames: int | None = None,
    *,
    solver_backend: str = DEFAULT_SOLVER_BACKEND,
) -> None:
    """Compatibility wrapper for the previous Phase D entrypoint name."""

    run_phase_f_app(max_frames=max_frames, solver_backend=solver_backend)


def run_phase_b_app(
    max_frames: int | None = None,
    *,
    solver_backend: str = DEFAULT_SOLVER_BACKEND,
) -> None:
    """Compatibility wrapper for the previous Phase B entrypoint name."""

    run_phase_f_app(max_frames=max_frames, solver_backend=solver_backend)


def run_phase_c_app(
    max_frames: int | None = None,
    *,
    solver_backend: str = DEFAULT_SOLVER_BACKEND,
) -> None:
    """Compatibility wrapper for the previous Phase C entrypoint name."""

    run_phase_f_app(max_frames=max_frames, solver_backend=solver_backend)


def run_phase_a_app(
    max_frames: int | None = None,
    *,
    solver_backend: str = DEFAULT_SOLVER_BACKEND,
) -> None:
    """Compatibility wrapper for the previous Phase A entrypoint name."""

    run_phase_f_app(max_frames=max_frames, solver_backend=solver_backend)
