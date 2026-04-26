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
_CENTER_OUTLINE_COLOR = (15, 17, 20)
_CELL_FILL_ALPHA = 140
_HOVER_CELL_COLOR = (255, 255, 255)
_SELECTED_CELL_COLOR = (61, 193, 211)
_VALIDATION_OK_COLOR = (88, 191, 116)
_VALIDATION_FAIL_COLOR = (226, 96, 96)
_HOVER_CENTER_RING_COLOR = (255, 255, 255)
_SELECTED_CENTER_RING_COLOR = (61, 193, 211)
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


def build_board_layout(
    puzzle_data: PuzzleData,
    *,
    cell_size: int = 72,
    padding: int = 24,
    label_gutter: int = 40,
    sidebar_width: int = 280,
) -> BoardLayout:
    """Return the fixed screen layout for one puzzle instance."""

    board_width = puzzle_data.board.cols * cell_size
    board_height = puzzle_data.board.rows * cell_size
    board_left = padding + label_gutter
    board_top = padding + label_gutter
    window_width = board_left + board_width + padding + sidebar_width + padding
    window_height = max(board_top + board_height + padding, 520)

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
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    """Draw the fixed puzzle board and its current editable state."""

    surface.fill(_BACKGROUND_COLOR)
    pygame.draw.rect(surface, _BOARD_COLOR, layout.board_rect, border_radius=12)
    pygame.draw.rect(surface, _PANEL_COLOR, layout.sidebar_rect, border_radius=12)

    _draw_assignment_fills(surface, puzzle.puzzle_data, layout, assigned_center_by_cell)
    _draw_cell_highlight(surface, layout, hovered_hit, _HOVER_CELL_COLOR, 2)
    _draw_cell_highlight(surface, layout, last_hit, _SELECTED_CELL_COLOR, 4)
    _draw_grid(surface, puzzle.puzzle_data, layout)
    _draw_axis_labels(surface, puzzle.puzzle_data, layout, body_font)
    _draw_centers(
        surface,
        puzzle.puzzle_data,
        layout,
        hovered_hit,
        selected_center_id,
        body_font,
    )
    _draw_sidebar(
        surface,
        puzzle,
        layout,
        assigned_center_by_cell,
        hovered_hit,
        last_hit,
        selected_center_id,
        validation_result,
        title_font,
        body_font,
        small_font,
    )


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

    phase_line = small_font.render("Phase D validates the live tentative assignment.", True, _SUBTEXT_COLOR)
    note_line = small_font.render("Select a center, then click cells to toggle them.", True, _SUBTEXT_COLOR)
    reset_line = small_font.render("Press R to clear the board state.", True, _SUBTEXT_COLOR)
    surface.blit(phase_line, (left, top))
    top += phase_line.get_height() + 4
    surface.blit(note_line, (left, top))
    top += note_line.get_height() + 4
    surface.blit(reset_line, (left, top))
    top += reset_line.get_height() + 18

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
