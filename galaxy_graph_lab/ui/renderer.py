from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pygame

try:
    from ..core import AssignmentValidationResult, Cell, CenterSpec, PuzzleData
except ImportError:
    from core import AssignmentValidationResult, Cell, CenterSpec, PuzzleData

from .puzzle_loader import FixedPuzzle


_BACKGROUND_COLOR = (24, 29, 36)
_PANEL_COLOR = (35, 43, 52)
_BOARD_COLOR = (247, 246, 242)
_GRID_COLOR = (90, 99, 112)
_LABEL_COLOR = (208, 214, 222)
_TEXT_COLOR = (233, 238, 243)
_SUBTEXT_COLOR = (172, 180, 190)
_DOMAIN_LABEL_COLOR = (156, 184, 255)
_CENTER_OUTLINE_COLOR = (15, 17, 20)
_CELL_FILL_ALPHA = 140
_DOMAIN_FILL_ALPHA = 50
_HOVER_CELL_COLOR = (255, 255, 255)
_SELECTED_CELL_COLOR = (61, 193, 211)
_VALIDATION_OK_COLOR = (88, 191, 116)
_VALIDATION_FAIL_COLOR = (226, 96, 96)
_KERNEL_COLOR = (255, 225, 102)
_BUTTON_COLOR = (61, 193, 211)
_BUTTON_HOVER_COLOR = (82, 215, 232)
_BUTTON_TEXT_COLOR = (15, 17, 20)
_SECONDARY_BUTTON_COLOR = (118, 129, 145)
_SECONDARY_BUTTON_HOVER_COLOR = (140, 151, 167)
_SECONDARY_BUTTON_DISABLED_COLOR = (75, 83, 94)
_MODE_MANUAL_COLOR = (118, 129, 145)
_MODE_SOLVER_COLOR = (88, 191, 116)
_MODE_MIXED_COLOR = (245, 179, 68)
_HOVER_CENTER_RING_COLOR = (255, 255, 255)
_SELECTED_CENTER_RING_COLOR = (61, 193, 211)
_COMPONENT_COLORS = (
    (255, 120, 120),
    (105, 196, 255),
    (120, 224, 147),
    (255, 198, 102),
)
_CENTER_COLORS = (
    (233, 106, 97),
    (80, 170, 120),
    (81, 152, 230),
    (245, 179, 68),
    (168, 112, 221),
    (77, 201, 206),
)


@dataclass(frozen=True, slots=True)
class BoardLayout:
    """Pixel layout for the board, labels, and side panel."""

    cell_size: int
    padding: int
    label_gutter: int
    sidebar_width: int
    board_left: int
    board_top: int
    board_width: int
    board_height: int
    window_width: int
    window_height: int

    @property
    def board_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.board_left,
            self.board_top,
            self.board_width,
            self.board_height,
        )

    @property
    def sidebar_rect(self) -> pygame.Rect:
        left = self.board_left + self.board_width + self.padding
        width = self.window_width - left - self.padding
        return pygame.Rect(left, self.padding, width, self.window_height - (2 * self.padding))


@dataclass(frozen=True, slots=True)
class GeometryHit:
    """One hit-test result for the read-only board geometry."""

    kind: str
    cell: Cell | None = None
    center_id: str | None = None


@dataclass(frozen=True, slots=True)
class DebugOverlayView:
    """Precomputed Phase F debug overlays and sidebar state."""

    show_admissible_domain: bool
    show_kernel_cells: bool
    show_components: bool
    show_solver_comparison: bool
    admissible_center_id: str | None
    admissible_cells: tuple[Cell, ...]
    kernel_cells_by_center: Mapping[str, tuple[Cell, ...]]
    component_index_by_cell: Mapping[Cell, int]
    solver_result_requested: bool
    solver_cached: bool
    solver_success: bool
    solver_status_label: str
    solver_message: str
    solution_visible: bool
    solution_loaded_into_board: bool
    board_mode_label: str
    show_solution_button_hovered: bool
    restore_manual_button_hovered: bool
    can_restore_manual_snapshot: bool
    comparison_by_cell: Mapping[Cell, bool]
    comparison_match_count: int | None
    comparison_mismatch_count: int | None


def build_board_layout(
    puzzle_data: PuzzleData,
    *,
    cell_size: int = 72,
    padding: int = 24,
    label_gutter: int = 40,
    sidebar_width: int = 360,
    window_size: tuple[int, int] | None = None,
) -> BoardLayout:
    """Return the fixed screen layout for one puzzle instance."""

    board_width = puzzle_data.board.cols * cell_size
    board_height = puzzle_data.board.rows * cell_size
    board_left = padding + label_gutter
    board_top = padding + label_gutter
    minimum_window_width = board_left + board_width + padding + sidebar_width + padding
    minimum_window_height = max(board_top + board_height + padding, 940)

    if window_size is None:
        window_width = minimum_window_width
        window_height = minimum_window_height
    else:
        window_width = max(minimum_window_width, int(window_size[0]))
        window_height = max(minimum_window_height, int(window_size[1]))

    return BoardLayout(
        cell_size=cell_size,
        padding=padding,
        label_gutter=label_gutter,
        sidebar_width=sidebar_width,
        board_left=board_left,
        board_top=board_top,
        board_width=board_width,
        board_height=board_height,
        window_width=window_width,
        window_height=window_height,
    )


def cell_rect(layout: BoardLayout, cell: Cell) -> pygame.Rect:
    return pygame.Rect(
        layout.board_left + (cell.col * layout.cell_size),
        layout.board_top + (cell.row * layout.cell_size),
        layout.cell_size,
        layout.cell_size,
    )


def center_position(layout: BoardLayout, center: CenterSpec) -> tuple[int, int]:
    col_coord = float(center.col_coord)
    row_coord = float(center.row_coord)
    x = layout.board_left + int((col_coord + 0.5) * layout.cell_size)
    y = layout.board_top + int((row_coord + 0.5) * layout.cell_size)
    return x, y


def center_radius(layout: BoardLayout) -> int:
    return max(12, layout.cell_size // 7)


def _center_color(index: int) -> tuple[int, int, int]:
    return _CENTER_COLORS[index % len(_CENTER_COLORS)]


def cell_at_pixel(
    puzzle_data: PuzzleData,
    layout: BoardLayout,
    pixel_position: tuple[int, int],
) -> Cell | None:
    """Return the board cell under one pixel position."""

    x, y = pixel_position
    if not layout.board_rect.collidepoint(x, y):
        return None

    col = (x - layout.board_left) // layout.cell_size
    row = (y - layout.board_top) // layout.cell_size
    if not puzzle_data.board.contains_indices(row, col):
        return None

    return Cell(row=row, col=col)


def center_at_pixel(
    puzzle_data: PuzzleData,
    layout: BoardLayout,
    pixel_position: tuple[int, int],
) -> CenterSpec | None:
    """Return the center marker hit by one pixel position."""

    x, y = pixel_position
    radius = center_radius(layout)

    for center in puzzle_data.centers:
        center_x, center_y = center_position(layout, center)
        dx = x - center_x
        dy = y - center_y
        if (dx * dx) + (dy * dy) <= radius * radius:
            return center

    return None


def hit_test_board_geometry(
    puzzle_data: PuzzleData,
    layout: BoardLayout,
    pixel_position: tuple[int, int],
) -> GeometryHit | None:
    """Return the clicked geometry target, prioritizing centers over cells."""

    center = center_at_pixel(puzzle_data, layout, pixel_position)
    if center is not None:
        return GeometryHit(kind="center", center_id=center.id)

    cell = cell_at_pixel(puzzle_data, layout, pixel_position)
    if cell is not None:
        return GeometryHit(kind="cell", cell=cell)

    return None


def draw_phase_a_scene(
    surface: pygame.Surface,
    puzzle: FixedPuzzle,
    layout: BoardLayout,
    assigned_center_by_cell: dict[Cell, str] | Mapping[Cell, str],
    hovered_hit: GeometryHit | None,
    last_hit: GeometryHit | None,
    selected_center_id: str | None,
    validation_result: AssignmentValidationResult,
    debug_view: DebugOverlayView,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    """Draw the fixed puzzle board and its current editable state."""

    surface.fill(_BACKGROUND_COLOR)
    pygame.draw.rect(surface, _BOARD_COLOR, layout.board_rect, border_radius=12)
    pygame.draw.rect(surface, _PANEL_COLOR, layout.sidebar_rect, border_radius=12)

    _draw_admissible_domain_overlay(
        surface,
        puzzle.puzzle_data,
        layout,
        debug_view.admissible_center_id,
        debug_view.admissible_cells,
    )
    _draw_board_mode_tint(surface, layout, debug_view.board_mode_label)
    _draw_assignment_fills(surface, puzzle.puzzle_data, layout, assigned_center_by_cell)
    _draw_kernel_highlights(surface, puzzle.puzzle_data, layout, debug_view.kernel_cells_by_center)
    _draw_grid(surface, puzzle.puzzle_data, layout)
    _draw_component_overlay(surface, layout, debug_view.component_index_by_cell)
    _draw_solution_comparison(surface, layout, debug_view.comparison_by_cell)
    _draw_cell_highlight(surface, layout, hovered_hit, _HOVER_CELL_COLOR, 2)
    _draw_cell_highlight(surface, layout, last_hit, _SELECTED_CELL_COLOR, 4)
    _draw_axis_labels(surface, puzzle.puzzle_data, layout, body_font)
    _draw_centers(
        surface,
        puzzle.puzzle_data,
        layout,
        hovered_hit,
        selected_center_id,
        body_font,
    )
    _draw_board_mode_badge(surface, layout, debug_view.board_mode_label, small_font)
    _draw_sidebar(
        surface,
        puzzle,
        layout,
        assigned_center_by_cell,
        hovered_hit,
        last_hit,
        selected_center_id,
        validation_result,
        debug_view,
        title_font,
        body_font,
        small_font,
    )


def show_solution_button_rect(
    layout: BoardLayout,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> pygame.Rect:
    left = layout.sidebar_rect.left + 18
    top = layout.sidebar_rect.top + 18
    top += title_font.get_height() + 16
    top += body_font.get_height() + 6
    top += body_font.get_height() + 20
    top += small_font.get_height() + 4
    top += small_font.get_height() + 4
    top += small_font.get_height() + 4
    top += small_font.get_height() + 18
    return pygame.Rect(left, top, layout.sidebar_rect.width - 36, 38)


def restore_manual_button_rect(
    layout: BoardLayout,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> pygame.Rect:
    show_rect = show_solution_button_rect(layout, title_font, body_font, small_font)
    return pygame.Rect(show_rect.left, show_rect.bottom + 10, show_rect.width, 34)


def _draw_grid(surface: pygame.Surface, puzzle_data: PuzzleData, layout: BoardLayout) -> None:
    for cell in puzzle_data.cells:
        pygame.draw.rect(surface, _GRID_COLOR, cell_rect(layout, cell), width=1, border_radius=3)

    pygame.draw.rect(surface, _GRID_COLOR, layout.board_rect, width=2, border_radius=12)


def _draw_assignment_fills(
    surface: pygame.Surface,
    puzzle_data: PuzzleData,
    layout: BoardLayout,
    assigned_center_by_cell: dict[Cell, str] | Mapping[Cell, str],
) -> None:
    fill_layer = pygame.Surface((layout.board_width, layout.board_height), pygame.SRCALPHA)
    center_index_by_id = {
        center.id: index
        for index, center in enumerate(puzzle_data.centers)
    }

    for cell, center_id in assigned_center_by_cell.items():
        rect = cell_rect(layout, cell).move(-layout.board_left, -layout.board_top)
        color = _center_color(center_index_by_id[center_id])
        fill_color = (*color, _CELL_FILL_ALPHA)
        pygame.draw.rect(fill_layer, fill_color, rect, border_radius=8)

    surface.blit(fill_layer, (layout.board_left, layout.board_top))


def _draw_board_mode_tint(
    surface: pygame.Surface,
    layout: BoardLayout,
    board_mode_label: str,
) -> None:
    if board_mode_label not in {"solver-loaded", "mixed"}:
        return

    tint_color = (
        (*_MODE_SOLVER_COLOR, 28)
        if board_mode_label == "solver-loaded"
        else (*_MODE_MIXED_COLOR, 24)
    )
    tint_layer = pygame.Surface((layout.board_width, layout.board_height), pygame.SRCALPHA)
    tint_layer.fill(tint_color)
    surface.blit(tint_layer, (layout.board_left, layout.board_top))


def _draw_admissible_domain_overlay(
    surface: pygame.Surface,
    puzzle_data: PuzzleData,
    layout: BoardLayout,
    center_id: str | None,
    admissible_cells: tuple[Cell, ...],
) -> None:
    if center_id is None or not admissible_cells:
        return

    color_lookup = {
        center.id: _center_color(index)
        for index, center in enumerate(puzzle_data.centers)
    }
    layer = pygame.Surface((layout.board_width, layout.board_height), pygame.SRCALPHA)
    fill_color = (*color_lookup[center_id], _DOMAIN_FILL_ALPHA)

    for cell in admissible_cells:
        rect = cell_rect(layout, cell).move(-layout.board_left, -layout.board_top)
        pygame.draw.rect(layer, fill_color, rect, border_radius=8)

    surface.blit(layer, (layout.board_left, layout.board_top))


def _draw_kernel_highlights(
    surface: pygame.Surface,
    puzzle_data: PuzzleData,
    layout: BoardLayout,
    kernel_cells_by_center: Mapping[str, tuple[Cell, ...]],
) -> None:
    if not kernel_cells_by_center:
        return

    center_index_by_id = {
        center.id: index
        for index, center in enumerate(puzzle_data.centers)
    }

    for center_id, cells in kernel_cells_by_center.items():
        color = _center_color(center_index_by_id[center_id])
        for cell in cells:
            rect = cell_rect(layout, cell).inflate(-28, -28)
            pygame.draw.rect(surface, _KERNEL_COLOR, rect, width=3, border_radius=6)
            pygame.draw.rect(surface, color, rect.inflate(-6, -6), width=2, border_radius=4)


def _draw_cell_highlight(
    surface: pygame.Surface,
    layout: BoardLayout,
    hit: GeometryHit | None,
    color: tuple[int, int, int],
    width: int,
) -> None:
    if hit is None or hit.kind != "cell" or hit.cell is None:
        return

    pygame.draw.rect(surface, color, cell_rect(layout, hit.cell), width=width, border_radius=6)


def _draw_component_overlay(
    surface: pygame.Surface,
    layout: BoardLayout,
    component_index_by_cell: Mapping[Cell, int],
) -> None:
    for cell, component_index in component_index_by_cell.items():
        color = _COMPONENT_COLORS[component_index % len(_COMPONENT_COLORS)]
        pygame.draw.rect(
            surface,
            color,
            cell_rect(layout, cell).inflate(-12, -12),
            width=3,
            border_radius=6,
        )


def _draw_solution_comparison(
    surface: pygame.Surface,
    layout: BoardLayout,
    comparison_by_cell: Mapping[Cell, bool],
) -> None:
    for cell, is_match in comparison_by_cell.items():
        color = _VALIDATION_OK_COLOR if is_match else _VALIDATION_FAIL_COLOR
        pygame.draw.rect(
            surface,
            color,
            cell_rect(layout, cell).inflate(-4, -4),
            width=2,
            border_radius=6,
        )


def _draw_board_mode_badge(
    surface: pygame.Surface,
    layout: BoardLayout,
    board_mode_label: str,
    font: pygame.font.Font,
) -> None:
    label_lookup = {
        "manual": ("Manual Board", _MODE_MANUAL_COLOR),
        "solver-loaded": ("Solver Solution Loaded", _MODE_SOLVER_COLOR),
        "mixed": ("Mixed: Solver + Manual Edits", _MODE_MIXED_COLOR),
    }
    label, color = label_lookup[board_mode_label]
    text = font.render(label, True, _TEXT_COLOR)
    rect = pygame.Rect(
        layout.board_left + 10,
        layout.board_top + 10,
        text.get_width() + 20,
        text.get_height() + 10,
    )
    pygame.draw.rect(surface, color, rect, border_radius=8)
    pygame.draw.rect(surface, _CENTER_OUTLINE_COLOR, rect, width=1, border_radius=8)
    surface.blit(text, (rect.left + 10, rect.top + 5))


def _draw_axis_labels(
    surface: pygame.Surface,
    puzzle_data: PuzzleData,
    layout: BoardLayout,
    font: pygame.font.Font,
) -> None:
    for col in range(puzzle_data.board.cols):
        label = font.render(str(col), True, _LABEL_COLOR)
        cell_left = layout.board_left + (col * layout.cell_size)
        label_x = cell_left + (layout.cell_size // 2) - (label.get_width() // 2)
        label_y = layout.padding
        surface.blit(label, (label_x, label_y))

    for row in range(puzzle_data.board.rows):
        label = font.render(str(row), True, _LABEL_COLOR)
        cell_top = layout.board_top + (row * layout.cell_size)
        label_x = layout.padding
        label_y = cell_top + (layout.cell_size // 2) - (label.get_height() // 2)
        surface.blit(label, (label_x, label_y))


def _draw_centers(
    surface: pygame.Surface,
    puzzle_data: PuzzleData,
    layout: BoardLayout,
    hovered_hit: GeometryHit | None,
    selected_center_id: str | None,
    font: pygame.font.Font,
) -> None:
    for index, center in enumerate(puzzle_data.centers):
        x, y = center_position(layout, center)
        radius = center_radius(layout)
        color = _center_color(index)
        pygame.draw.circle(surface, color, (x, y), radius)
        pygame.draw.circle(surface, _CENTER_OUTLINE_COLOR, (x, y), radius, width=2)
        if hovered_hit is not None and hovered_hit.kind == "center" and hovered_hit.center_id == center.id:
            pygame.draw.circle(surface, _HOVER_CENTER_RING_COLOR, (x, y), radius + 4, width=2)
        if selected_center_id == center.id:
            pygame.draw.circle(surface, _SELECTED_CENTER_RING_COLOR, (x, y), radius + 8, width=3)

        label = font.render(center.id, True, _CENTER_OUTLINE_COLOR)
        label_x = x - (label.get_width() // 2)
        label_y = y - (label.get_height() // 2)
        surface.blit(label, (label_x, label_y))


def _draw_sidebar(
    surface: pygame.Surface,
    puzzle: FixedPuzzle,
    layout: BoardLayout,
    assigned_center_by_cell: dict[Cell, str] | Mapping[Cell, str],
    hovered_hit: GeometryHit | None,
    last_hit: GeometryHit | None,
    selected_center_id: str | None,
    validation_result: AssignmentValidationResult,
    debug_view: DebugOverlayView,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    left = layout.sidebar_rect.left + 18
    top = layout.sidebar_rect.top + 18

    title = title_font.render(puzzle.name, True, _TEXT_COLOR)
    surface.blit(title, (left, top))
    top += title.get_height() + 16

    rows_line = body_font.render(
        f"Board: {puzzle.puzzle_data.board.rows} x {puzzle.puzzle_data.board.cols}",
        True,
        _TEXT_COLOR,
    )
    centers_line = body_font.render(
        f"Centers: {len(puzzle.puzzle_data.centers)}",
        True,
        _TEXT_COLOR,
    )
    surface.blit(rows_line, (left, top))
    top += rows_line.get_height() + 6
    surface.blit(centers_line, (left, top))
    top += centers_line.get_height() + 20

    phase_line = small_font.render("Phase F adds solver and geometry debug overlays.", True, _SUBTEXT_COLOR)
    note_line = small_font.render("Select a center, then click cells to toggle them.", True, _SUBTEXT_COLOR)
    reset_line = small_font.render("R reset | A domain | K kernel | C comps", True, _SUBTEXT_COLOR)
    solver_line = small_font.render("Show Solution | H restore | S solve | M compare", True, _SUBTEXT_COLOR)
    surface.blit(phase_line, (left, top))
    top += phase_line.get_height() + 4
    surface.blit(note_line, (left, top))
    top += note_line.get_height() + 4
    surface.blit(reset_line, (left, top))
    top += reset_line.get_height() + 4
    surface.blit(solver_line, (left, top))
    top += solver_line.get_height() + 18

    button_rect = show_solution_button_rect(layout, title_font, body_font, small_font)
    _draw_show_solution_button(
        surface,
        button_rect,
        body_font,
        debug_view.show_solution_button_hovered,
    )
    restore_rect = restore_manual_button_rect(layout, title_font, body_font, small_font)
    _draw_secondary_button(
        surface,
        restore_rect,
        body_font,
        "Restore Manual",
        debug_view.restore_manual_button_hovered,
        debug_view.can_restore_manual_snapshot,
    )
    top = restore_rect.bottom + 18

    selected_title = body_font.render("Selected Center", True, _TEXT_COLOR)
    surface.blit(selected_title, (left, top))
    top += selected_title.get_height() + 6
    selected_center_label = small_font.render(
        selected_center_id if selected_center_id is not None else "None",
        True,
        _TEXT_COLOR,
    )
    surface.blit(selected_center_label, (left, top))
    top += selected_center_label.get_height() + 14

    hovered_title = body_font.render("Hover", True, _TEXT_COLOR)
    surface.blit(hovered_title, (left, top))
    top += hovered_title.get_height() + 6
    hovered_label = small_font.render(_hit_label(hovered_hit), True, _TEXT_COLOR)
    surface.blit(hovered_label, (left, top))
    top += hovered_label.get_height() + 14

    last_click_title = body_font.render("Last Click", True, _TEXT_COLOR)
    surface.blit(last_click_title, (left, top))
    top += last_click_title.get_height() + 6
    last_click_label = small_font.render(_hit_label(last_hit), True, _TEXT_COLOR)
    surface.blit(last_click_label, (left, top))
    top += last_click_label.get_height() + 18

    validation_title = body_font.render("Validation", True, _TEXT_COLOR)
    surface.blit(validation_title, (left, top))
    top += validation_title.get_height() + 10

    overall_label = "VALID" if validation_result.is_valid else "INVALID"
    overall_color = _VALIDATION_OK_COLOR if validation_result.is_valid else _VALIDATION_FAIL_COLOR
    overall_text = small_font.render(f"Overall: {overall_label}", True, overall_color)
    surface.blit(overall_text, (left, top))
    top += overall_text.get_height() + 10

    validation_rows = (
        ("Partition", validation_result.partition_ok),
        ("Admissibility", validation_result.admissibility_ok),
        ("Symmetry", validation_result.symmetry_ok),
        ("Kernel", validation_result.kernel_ok),
        ("Connectivity", validation_result.connectivity_ok),
    )
    for label, is_ok in validation_rows:
        _draw_validation_row(surface, small_font, left, top, label, is_ok)
        top += 22

    top += 12
    debug_title = body_font.render("Debug Tools", True, _TEXT_COLOR)
    surface.blit(debug_title, (left, top))
    top += debug_title.get_height() + 10

    debug_rows = (
        ("Admissible Domain", debug_view.show_admissible_domain),
        ("Kernel Cells", debug_view.show_kernel_cells),
        ("Selected Components", debug_view.show_components),
        ("Compare vs Solver", debug_view.show_solver_comparison),
    )
    for label, is_on in debug_rows:
        _draw_toggle_row(surface, small_font, left, top, label, is_on)
        top += 22

    top += 10
    solver_title = body_font.render("Solver Session", True, _TEXT_COLOR)
    surface.blit(solver_title, (left, top))
    top += solver_title.get_height() + 8

    status_label_lookup = {
        "not_requested": "Not Requested",
        "solved": "Solved",
        "infeasible": "No Feasible Solution",
        "solver_error": "Solver Error",
        "backend_unavailable": "Solver Unavailable",
        "unsupported_backend": "Unsupported Backend",
    }
    if debug_view.solver_status_label == "solved":
        status_color = _VALIDATION_OK_COLOR
    elif debug_view.solver_result_requested:
        status_color = _VALIDATION_FAIL_COLOR
    else:
        status_color = _SUBTEXT_COLOR
    status_line = small_font.render(
        f"Status: {status_label_lookup.get(debug_view.solver_status_label, debug_view.solver_status_label)}",
        True,
        status_color,
    )
    surface.blit(status_line, (left, top))
    top += status_line.get_height() + 6

    session_rows = (
        ("Requested", debug_view.solver_result_requested),
        ("Cached", debug_view.solver_cached),
        ("Solution Visible", debug_view.solution_visible),
        ("Loaded Into Board", debug_view.solution_loaded_into_board),
    )
    for label, is_on in session_rows:
        _draw_toggle_row(surface, small_font, left, top, label, is_on)
        top += 22

    board_mode_display_lookup = {
        "manual": "Manual",
        "solver-loaded": "Solver Loaded",
        "mixed": "Mixed",
    }
    board_source_line = small_font.render(
        f"Board Mode: {board_mode_display_lookup[debug_view.board_mode_label]}",
        True,
        _TEXT_COLOR,
    )
    surface.blit(board_source_line, (left, top))
    top += board_source_line.get_height() + 8

    for line in _wrap_text(debug_view.solver_message, 34):
        message_line = small_font.render(line, True, _SUBTEXT_COLOR)
        surface.blit(message_line, (left, top))
        top += message_line.get_height() + 4

    if debug_view.show_admissible_domain and debug_view.admissible_center_id is None:
        domain_hint = small_font.render("Domain overlay waits for a selected center.", True, _DOMAIN_LABEL_COLOR)
        surface.blit(domain_hint, (left, top))
        top += domain_hint.get_height() + 6

    if debug_view.show_components and selected_center_id is None:
        component_hint = small_font.render("Component overlay follows the selected center.", True, _SUBTEXT_COLOR)
        surface.blit(component_hint, (left, top))
        top += component_hint.get_height() + 6

    if debug_view.comparison_match_count is not None and debug_view.comparison_mismatch_count is not None:
        matches_line = small_font.render(
            f"Matches: {debug_view.comparison_match_count}",
            True,
            _VALIDATION_OK_COLOR,
        )
        mismatches_line = small_font.render(
            f"Mismatches: {debug_view.comparison_mismatch_count}",
            True,
            _VALIDATION_FAIL_COLOR,
        )
        surface.blit(matches_line, (left, top))
        top += matches_line.get_height() + 4
        surface.blit(mismatches_line, (left, top))
        top += mismatches_line.get_height() + 10

    top += 12
    assigned_title = body_font.render("Assigned Cells", True, _TEXT_COLOR)
    surface.blit(assigned_title, (left, top))
    top += assigned_title.get_height() + 10

    centers_title = body_font.render("Centers", True, _TEXT_COLOR)
    surface.blit(centers_title, (left, top))
    top += centers_title.get_height() + 12

    counts_by_center = {
        center.id: 0
        for center in puzzle.puzzle_data.centers
    }
    for center_id in assigned_center_by_cell.values():
        counts_by_center[center_id] += 1

    for index, center in enumerate(puzzle.puzzle_data.centers):
        color = _center_color(index)
        pygame.draw.circle(surface, color, (left + 10, top + 10), 8)
        pygame.draw.circle(surface, _CENTER_OUTLINE_COLOR, (left + 10, top + 10), 8, width=1)
        if selected_center_id == center.id:
            pygame.draw.circle(surface, _SELECTED_CENTER_RING_COLOR, (left + 10, top + 10), 11, width=2)

        label = small_font.render(
            (
                f"{center.id}: ({float(center.row_coord)}, {float(center.col_coord)})"
                f" [{counts_by_center[center.id]}]"
            ),
            True,
            _TEXT_COLOR,
        )
        surface.blit(label, (left + 26, top + 1))
        top += 24


def _hit_label(hit: GeometryHit | None) -> str:
    if hit is None:
        return "None"
    if hit.kind == "cell" and hit.cell is not None:
        return f"Cell ({hit.cell.row}, {hit.cell.col})"
    if hit.kind == "center" and hit.center_id is not None:
        return f"Center {hit.center_id}"
    return "None"


def _draw_validation_row(
    surface: pygame.Surface,
    font: pygame.font.Font,
    left: int,
    top: int,
    label: str,
    is_ok: bool,
) -> None:
    color = _VALIDATION_OK_COLOR if is_ok else _VALIDATION_FAIL_COLOR
    status = "OK" if is_ok else "FAIL"
    pygame.draw.circle(surface, color, (left + 7, top + 9), 5)
    text = font.render(f"{label}: {status}", True, _TEXT_COLOR)
    surface.blit(text, (left + 20, top))


def _draw_toggle_row(
    surface: pygame.Surface,
    font: pygame.font.Font,
    left: int,
    top: int,
    label: str,
    is_on: bool,
) -> None:
    color = _VALIDATION_OK_COLOR if is_on else _SUBTEXT_COLOR
    status = "ON" if is_on else "OFF"
    pygame.draw.circle(surface, color, (left + 7, top + 9), 5)
    text = font.render(f"{label}: {status}", True, _TEXT_COLOR)
    surface.blit(text, (left + 20, top))


def _draw_show_solution_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    font: pygame.font.Font,
    is_hovered: bool,
) -> None:
    color = _BUTTON_HOVER_COLOR if is_hovered else _BUTTON_COLOR
    pygame.draw.rect(surface, color, rect, border_radius=8)
    pygame.draw.rect(surface, _CENTER_OUTLINE_COLOR, rect, width=2, border_radius=8)
    label = font.render("Show Solution", True, _BUTTON_TEXT_COLOR)
    label_x = rect.centerx - (label.get_width() // 2)
    label_y = rect.centery - (label.get_height() // 2)
    surface.blit(label, (label_x, label_y))


def _draw_secondary_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    font: pygame.font.Font,
    label_text: str,
    is_hovered: bool,
    is_enabled: bool,
) -> None:
    if not is_enabled:
        color = _SECONDARY_BUTTON_DISABLED_COLOR
    else:
        color = _SECONDARY_BUTTON_HOVER_COLOR if is_hovered else _SECONDARY_BUTTON_COLOR
    pygame.draw.rect(surface, color, rect, border_radius=8)
    pygame.draw.rect(surface, _CENTER_OUTLINE_COLOR, rect, width=2, border_radius=8)
    label = font.render(label_text, True, _TEXT_COLOR)
    label_x = rect.centerx - (label.get_width() // 2)
    label_y = rect.centery - (label.get_height() // 2)
    surface.blit(label, (label_x, label_y))


def _wrap_text(text: str, max_chars: int) -> tuple[str, ...]:
    words = text.split()
    if not words:
        return ("",)

    lines: list[str] = []
    current_line = words[0]
    for word in words[1:]:
        candidate = f"{current_line} {word}"
        if len(candidate) <= max_chars:
            current_line = candidate
            continue
        lines.append(current_line)
        current_line = word
    lines.append(current_line)
    return tuple(lines)
