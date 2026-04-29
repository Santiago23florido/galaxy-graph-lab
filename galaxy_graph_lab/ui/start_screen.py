from __future__ import annotations

from dataclasses import dataclass

import pygame

from ..core import BoardSpec, PuzzleGenerationRequest, difficulty_profile_for, difficulty_profiles


_BACKGROUND_COLOR = (18, 17, 26)
_GRID_COLOR = (39, 36, 51)
_OUTER_BORDER_COLOR = (82, 88, 120)
_PANEL_COLOR = (34, 31, 41)
_PANEL_BORDER_COLOR = (70, 67, 84)
_SECTION_PANEL_COLOR = (28, 26, 35)
_SECTION_PANEL_ALT_COLOR = (24, 22, 31)
_TEXT_COLOR = (241, 238, 247)
_SUBTEXT_COLOR = (177, 172, 189)
_MUTED_TEXT_COLOR = (119, 115, 132)
_BUTTON_COLOR = (188, 170, 244)
_BUTTON_HOVER_COLOR = (203, 188, 250)
_BUTTON_IDLE_COLOR = (44, 41, 54)
_BUTTON_IDLE_HOVER_COLOR = (58, 54, 71)
_BUTTON_SELECTED_COLOR = (188, 170, 244)
_BUTTON_SELECTED_HOVER_COLOR = (203, 188, 250)
_BUTTON_TEXT_COLOR = (34, 26, 55)
_BUTTON_IDLE_TEXT_COLOR = (241, 238, 247)
_BORDER_COLOR = (119, 111, 145)
_ACCENT_COLOR = (111, 214, 226)

_DEFAULT_WINDOW_WIDTH = 1280
_DEFAULT_WINDOW_HEIGHT = 820
_MIN_WINDOW_WIDTH = 980
_MIN_WINDOW_HEIGHT = 820


@dataclass(frozen=True, slots=True)
class StartScreenLayout:
    """Fixed pixel layout for the Pygame start screen."""

    window_width: int
    window_height: int
    padding: int
    panel_width: int
    panel_height: int

    @property
    def panel_rect(self) -> pygame.Rect:
        left = (self.window_width - self.panel_width) // 2
        top = (self.window_height - self.panel_height) // 2
        return pygame.Rect(left, top, self.panel_width, self.panel_height)

    @property
    def frame_rect(self) -> pygame.Rect:
        return pygame.Rect(8, 8, self.window_width - 16, self.window_height - 16)


@dataclass(frozen=True, slots=True)
class StartScreenHit:
    """One hit-test result for the start screen controls."""

    kind: str
    difficulty: str | None = None
    grid_size: BoardSpec | None = None


@dataclass(slots=True)
class StartScreenState:
    """Mutable selection state for the pre-game generation screen."""

    selected_difficulty: str
    selected_grid_size: BoardSpec
    status_message: str = "Select a difficulty and grid size, then generate a puzzle."

    @property
    def available_grid_sizes(self) -> tuple[BoardSpec, ...]:
        return difficulty_profile_for(self.selected_difficulty).allowed_grid_sizes

    def select_difficulty(self, difficulty: str) -> None:
        profile = difficulty_profile_for(difficulty)
        self.selected_difficulty = difficulty
        if self.selected_grid_size not in profile.allowed_grid_sizes:
            self.selected_grid_size = profile.allowed_grid_sizes[0]
        self.status_message = "Select a difficulty and grid size, then generate a puzzle."

    def select_grid_size(self, grid_size: BoardSpec) -> None:
        if grid_size not in self.available_grid_sizes:
            raise ValueError("grid_size is not allowed for the selected difficulty.")
        self.selected_grid_size = grid_size
        self.status_message = "Select a difficulty and grid size, then generate a puzzle."


def build_start_screen_layout(
    window_size: tuple[int, int] | None = None,
) -> StartScreenLayout:
    """Return the responsive layout for the start screen scene."""

    if window_size is None:
        window_width = _DEFAULT_WINDOW_WIDTH
        window_height = _DEFAULT_WINDOW_HEIGHT
    else:
        window_width = max(_MIN_WINDOW_WIDTH, int(window_size[0]))
        window_height = max(_MIN_WINDOW_HEIGHT, int(window_size[1]))

    panel_width = min(1020, window_width - 80)
    panel_height = min(660, window_height - 80)

    return StartScreenLayout(
        window_width=window_width,
        window_height=window_height,
        padding=24,
        panel_width=panel_width,
        panel_height=panel_height,
    )


def default_start_screen_state() -> StartScreenState:
    """Return the initial start-screen state from the first difficulty profile."""

    first_profile = difficulty_profiles()[0]
    return StartScreenState(
        selected_difficulty=first_profile.difficulty,
        selected_grid_size=first_profile.allowed_grid_sizes[0],
    )


def build_generation_request_from_state(
    state: StartScreenState,
    *,
    random_seed: int | None = None,
    max_generation_retries: int = 1,
) -> PuzzleGenerationRequest:
    """Build one validated generation request from the current UI selection."""

    return PuzzleGenerationRequest(
        difficulty=state.selected_difficulty,
        grid_size=state.selected_grid_size,
        random_seed=random_seed,
        max_generation_retries=max_generation_retries,
    )


def difficulty_button_rects(layout: StartScreenLayout) -> dict[str, pygame.Rect]:
    section = _difficulty_section_rect(layout)
    top = section.top + 52
    gap = 12
    width = (section.width - (2 * gap)) // 3
    height = 52
    total_width = (3 * width) + (2 * gap)
    left = section.left + ((section.width - total_width) // 2)

    return {
        profile.difficulty: pygame.Rect(
            left + (index * (width + gap)),
            top,
            width,
            height,
        )
        for index, profile in enumerate(difficulty_profiles())
    }


def grid_size_button_rects(
    layout: StartScreenLayout,
    state: StartScreenState,
) -> dict[BoardSpec, pygame.Rect]:
    section = _grid_section_rect(layout)
    top = section.top + 52
    gap = 12
    button_count = len(state.available_grid_sizes)
    width = (section.width - (gap * max(0, button_count - 1))) // button_count
    height = 52
    total_width = (button_count * width) + (max(0, button_count - 1) * gap)
    left = section.left + ((section.width - total_width) // 2)

    return {
        grid_size: pygame.Rect(
            left + (index * (width + gap)),
            top,
            width,
            height,
        )
        for index, grid_size in enumerate(state.available_grid_sizes)
    }


def generate_puzzle_button_rect(layout: StartScreenLayout) -> pygame.Rect:
    panel = layout.panel_rect
    return pygame.Rect(
        panel.left + 48,
        panel.bottom - 88,
        panel.width - 96,
        56,
    )


def hit_test_start_screen(
    layout: StartScreenLayout,
    state: StartScreenState,
    pixel_position: tuple[int, int],
) -> StartScreenHit | None:
    """Return the clicked start-screen control, if any."""

    for difficulty, rect in difficulty_button_rects(layout).items():
        if rect.collidepoint(pixel_position):
            return StartScreenHit(kind="difficulty", difficulty=difficulty)

    for grid_size, rect in grid_size_button_rects(layout, state).items():
        if rect.collidepoint(pixel_position):
            return StartScreenHit(kind="grid_size", grid_size=grid_size)

    if generate_puzzle_button_rect(layout).collidepoint(pixel_position):
        return StartScreenHit(kind="generate")

    return None


def apply_start_screen_hit(
    state: StartScreenState,
    hit: StartScreenHit | None,
) -> None:
    """Apply one start-screen selection change from the current hit result."""

    if hit is None:
        return
    if hit.kind == "difficulty" and hit.difficulty is not None:
        state.select_difficulty(hit.difficulty)
        return
    if hit.kind == "grid_size" and hit.grid_size is not None:
        state.select_grid_size(hit.grid_size)


def draw_start_screen(
    surface: pygame.Surface,
    layout: StartScreenLayout,
    state: StartScreenState,
    hovered_hit: StartScreenHit | None,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    """Draw the initial start screen for difficulty and grid-size selection."""

    _draw_background(surface, layout)
    _draw_panel(surface, layout)

    panel = layout.panel_rect
    center_x = panel.centerx
    selection_rect = _selection_card_rect(layout)
    profile_rect = _profile_card_rect(layout)
    subtitle_width = min(panel.width - 180, 620)

    eyebrow = small_font.render("GALAXY GRAPH LAB", True, _MUTED_TEXT_COLOR)
    eyebrow_rect = eyebrow.get_rect(center=(center_x, panel.top + 48))
    surface.blit(eyebrow, eyebrow_rect)

    title = title_font.render("Choose Your Puzzle Profile", True, _TEXT_COLOR)
    title_rect = title.get_rect(center=(center_x, eyebrow_rect.bottom + 30))
    surface.blit(title, title_rect)

    subtitle_rect = pygame.Rect(
        center_x - (subtitle_width // 2),
        title_rect.bottom + 14,
        subtitle_width,
        52,
    )
    _draw_centered_text_block(
        surface,
        (
            "Select a preset and board size before launching a certified puzzle."
        ),
        body_font,
        _SUBTEXT_COLOR,
        subtitle_rect,
        line_gap=4,
    )

    _draw_surface_panel(surface, selection_rect)
    _draw_surface_panel(surface, profile_rect)

    _draw_section_heading(
        surface,
        _difficulty_section_rect(layout),
        "Difficulty",
        "Controls center density and structural pressure.",
        body_font,
        small_font,
    )

    for difficulty, rect in difficulty_button_rects(layout).items():
        is_selected = difficulty == state.selected_difficulty
        is_hovered = (
            hovered_hit is not None
            and hovered_hit.kind == "difficulty"
            and hovered_hit.difficulty == difficulty
        )
        _draw_option_button(
            surface,
            rect,
            difficulty.title(),
            body_font,
            is_selected=is_selected,
            is_hovered=is_hovered,
        )

    _draw_section_heading(
        surface,
        _grid_section_rect(layout),
        "Grid Size",
        "Sets the playing field before generation starts.",
        body_font,
        small_font,
    )

    for grid_size, rect in grid_size_button_rects(layout, state).items():
        is_selected = grid_size == state.selected_grid_size
        is_hovered = (
            hovered_hit is not None
            and hovered_hit.kind == "grid_size"
            and hovered_hit.grid_size == grid_size
        )
        _draw_option_button(
            surface,
            rect,
            f"{grid_size.rows} x {grid_size.cols}",
            body_font,
            is_selected=is_selected,
            is_hovered=is_hovered,
        )

    profile = difficulty_profile_for(state.selected_difficulty)
    _draw_selection_footer(surface, layout, body_font, small_font)
    _draw_profile_panel(surface, layout, profile, title_font, body_font, small_font, state)

    generate_rect = generate_puzzle_button_rect(layout)
    is_generate_hovered = hovered_hit is not None and hovered_hit.kind == "generate"
    _draw_primary_button(
        surface,
        generate_rect,
        "Generate Puzzle",
        body_font,
        is_hovered=is_generate_hovered,
    )

    message_lines = _wrap_text(state.status_message, 92)
    message_top = generate_rect.bottom + 14
    for index, line in enumerate(message_lines):
        message = small_font.render(line, True, _MUTED_TEXT_COLOR)
        message_rect = message.get_rect(center=(panel.centerx, message_top + (index * 22)))
        surface.blit(message, message_rect)


def _draw_background(surface: pygame.Surface, layout: StartScreenLayout) -> None:
    surface.fill(_BACKGROUND_COLOR)

    for x in range(0, layout.window_width, 40):
        pygame.draw.line(surface, _GRID_COLOR, (x, 0), (x, layout.window_height), 1)
    for y in range(0, layout.window_height, 40):
        pygame.draw.line(surface, _GRID_COLOR, (0, y), (layout.window_width, y), 1)

    pygame.draw.rect(surface, _OUTER_BORDER_COLOR, layout.frame_rect, width=2, border_radius=16)


def _draw_panel(surface: pygame.Surface, layout: StartScreenLayout) -> None:
    shadow_rect = layout.panel_rect.move(0, 10)
    shadow_surface = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(
        shadow_surface,
        (0, 0, 0, 80),
        shadow_surface.get_rect(),
        border_radius=18,
    )
    surface.blit(shadow_surface, shadow_rect.topleft)

    pygame.draw.rect(surface, _PANEL_COLOR, layout.panel_rect, border_radius=18)
    pygame.draw.rect(surface, _PANEL_BORDER_COLOR, layout.panel_rect, width=2, border_radius=18)

    dot_y = layout.panel_rect.top + 18
    dot_x = layout.panel_rect.right - 36
    for offset in (0, 12, 24):
        pygame.draw.circle(surface, _MUTED_TEXT_COLOR, (dot_x + offset, dot_y), 3)


def _selection_card_rect(layout: StartScreenLayout) -> pygame.Rect:
    panel = layout.panel_rect
    generate_rect = generate_puzzle_button_rect(layout)
    content_left = panel.left + 48
    content_top = panel.top + 154
    content_bottom = generate_rect.top - 18
    content_width = panel.width - 96
    gap = 24
    left_width = min(430, (content_width - gap) // 2)
    return pygame.Rect(
        content_left,
        content_top,
        left_width,
        content_bottom - content_top,
    )


def _profile_card_rect(layout: StartScreenLayout) -> pygame.Rect:
    panel = layout.panel_rect
    selection_rect = _selection_card_rect(layout)
    generate_rect = generate_puzzle_button_rect(layout)
    left = selection_rect.right + 24
    right = panel.right - 48
    return pygame.Rect(
        left,
        selection_rect.top,
        right - left,
        generate_rect.top - 18 - selection_rect.top,
    )


def _difficulty_section_rect(layout: StartScreenLayout) -> pygame.Rect:
    selection_rect = _selection_card_rect(layout)
    return pygame.Rect(
        selection_rect.left + 20,
        selection_rect.top + 20,
        selection_rect.width - 40,
        122,
    )


def _grid_section_rect(layout: StartScreenLayout) -> pygame.Rect:
    selection_rect = _selection_card_rect(layout)
    return pygame.Rect(
        selection_rect.left + 20,
        selection_rect.top + 160,
        selection_rect.width - 40,
        122,
    )


def _selection_footer_rect(layout: StartScreenLayout) -> pygame.Rect:
    selection_rect = _selection_card_rect(layout)
    return pygame.Rect(
        selection_rect.left + 20,
        selection_rect.top + 300,
        selection_rect.width - 40,
        selection_rect.height - 320,
    )


def _draw_surface_panel(surface: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(surface, _SECTION_PANEL_COLOR, rect, border_radius=16)
    pygame.draw.rect(surface, _PANEL_BORDER_COLOR, rect, width=1, border_radius=16)


def _draw_section_heading(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    caption: str,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    heading = body_font.render(label, True, _TEXT_COLOR)
    surface.blit(heading, (rect.left, rect.top))

    caption_surface = small_font.render(caption, True, _MUTED_TEXT_COLOR)
    surface.blit(caption_surface, (rect.left, rect.top + 28))

    pygame.draw.line(
        surface,
        _ACCENT_COLOR,
        (rect.left, rect.top + 58),
        (rect.left + 42, rect.top + 58),
        3,
    )


def _draw_profile_panel(
    surface: pygame.Surface,
    layout: StartScreenLayout,
    profile,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
    state: StartScreenState,
) -> None:
    rect = _profile_card_rect(layout)

    heading = body_font.render("Generation Snapshot", True, _TEXT_COLOR)
    surface.blit(heading, (rect.left + 20, rect.top + 18))

    snapshot = title_font.render(
        f"{state.selected_difficulty.title()}  •  {state.selected_grid_size.rows}x{state.selected_grid_size.cols}",
        True,
        _TEXT_COLOR,
    )
    surface.blit(snapshot, (rect.left + 20, rect.top + 50))

    note_rect = pygame.Rect(rect.left + 20, rect.top + 88, rect.width - 40, 24)
    _draw_text_block(
        surface,
        "Certified profile for connected galaxy generation.",
        small_font,
        _SUBTEXT_COLOR,
        note_rect,
        line_gap=2,
    )

    badge_top = rect.top + 116
    badge_left = rect.left + 20
    certified_rect = _badge_rect(badge_left, badge_top, "Certified", small_font)
    _draw_badge(surface, certified_rect, "Certified", small_font, is_primary=True)

    uniqueness_label = "Unique solution" if profile.uniqueness_required else "Flexible solution"
    uniqueness_rect = _badge_rect(certified_rect.right + 10, badge_top, uniqueness_label, small_font)
    _draw_badge(surface, uniqueness_rect, uniqueness_label, small_font, is_primary=False)

    stats = (
        ("Allowed sizes", ", ".join(f"{size.rows}x{size.cols}" for size in profile.allowed_grid_sizes)),
        ("Centers", f"{profile.min_center_count} to {profile.max_center_count}"),
        (
            "Overlap target",
            (
                f"{int(profile.overlap_target_range.min_ratio * 100)}% to "
                f"{int(profile.overlap_target_range.max_ratio * 100)}%"
            ),
        ),
        (
            "Irregularity",
            (
                f"{int(profile.irregularity_target_range.min_ratio * 100)}% to "
                f"{int(profile.irregularity_target_range.max_ratio * 100)}%"
            ),
        ),
    )

    stat_top = rect.top + 156
    stat_gap = 12
    stat_width = (rect.width - 52) // 2
    stat_height = 72

    for index, (label, value) in enumerate(stats):
        column = index % 2
        row = index // 2
        stat_rect = pygame.Rect(
            rect.left + 20 + (column * (stat_width + stat_gap)),
            stat_top + (row * (stat_height + stat_gap)),
            stat_width,
            stat_height,
        )
        _draw_stat_card(surface, stat_rect, label, value, body_font, small_font)

    mix_rect = pygame.Rect(
        rect.left + 20,
        stat_top + (2 * (stat_height + stat_gap)),
        rect.width - 40,
        rect.bottom - 20 - (stat_top + (2 * (stat_height + stat_gap))),
    )
    _draw_mix_card(surface, mix_rect, profile, body_font, small_font)


def _draw_selection_footer(
    surface: pygame.Surface,
    layout: StartScreenLayout,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    rect = _selection_footer_rect(layout)
    if rect.height <= 0:
        return

    heading = body_font.render("Generator Focus", True, _TEXT_COLOR)
    surface.blit(heading, (rect.left, rect.top))

    badge_top = rect.top + 34
    badge_left = rect.left
    for label, is_primary in (
        ("Symmetry", False),
        ("Connectivity", False),
        ("Uniqueness", True),
    ):
        badge = _badge_rect(badge_left, badge_top, label, small_font)
        _draw_badge(surface, badge, label, small_font, is_primary=is_primary)
        badge_left = badge.right + 10

    text_rect = pygame.Rect(rect.left, rect.top + 72, rect.width, max(0, rect.height - 72))
    _draw_text_block(
        surface,
        "The selected preset shapes center counts, overlap, and region irregularity before generation begins.",
        small_font,
        _SUBTEXT_COLOR,
        text_rect,
        line_gap=3,
    )


def _draw_option_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    is_selected: bool,
    is_hovered: bool,
) -> None:
    if is_selected:
        color = _BUTTON_SELECTED_HOVER_COLOR if is_hovered else _BUTTON_SELECTED_COLOR
        text_color = _BUTTON_TEXT_COLOR
    else:
        color = _BUTTON_IDLE_HOVER_COLOR if is_hovered else _BUTTON_IDLE_COLOR
        text_color = _BUTTON_IDLE_TEXT_COLOR
    pygame.draw.rect(surface, color, rect, border_radius=10)
    border_color = _BUTTON_SELECTED_COLOR if is_selected else _BORDER_COLOR
    pygame.draw.rect(surface, border_color, rect, width=2, border_radius=10)
    label_surface = font.render(label, True, text_color)
    surface.blit(
        label_surface,
        (
            rect.centerx - (label_surface.get_width() // 2),
            rect.centery - (label_surface.get_height() // 2),
        ),
    )


def _draw_primary_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    is_hovered: bool,
) -> None:
    color = _BUTTON_HOVER_COLOR if is_hovered else _BUTTON_COLOR
    pygame.draw.rect(surface, color, rect, border_radius=10)
    pygame.draw.rect(surface, _PANEL_BORDER_COLOR, rect, width=2, border_radius=10)
    label_surface = font.render(label, True, _BUTTON_TEXT_COLOR)
    surface.blit(
        label_surface,
        (
            rect.centerx - (label_surface.get_width() // 2),
            rect.centery - (label_surface.get_height() // 2),
        ),
    )


def _badge_rect(left: int, top: int, label: str, font: pygame.font.Font) -> pygame.Rect:
    width = font.size(label)[0] + 26
    return pygame.Rect(left, top, width, 28)


def _draw_badge(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    is_primary: bool,
) -> None:
    fill_color = _BUTTON_SELECTED_COLOR if is_primary else _SECTION_PANEL_ALT_COLOR
    text_color = _BUTTON_TEXT_COLOR if is_primary else _SUBTEXT_COLOR
    border_color = _BUTTON_SELECTED_COLOR if is_primary else _PANEL_BORDER_COLOR
    pygame.draw.rect(surface, fill_color, rect, border_radius=14)
    pygame.draw.rect(surface, border_color, rect, width=1, border_radius=14)
    label_surface = font.render(label, True, text_color)
    surface.blit(
        label_surface,
        (
            rect.centerx - (label_surface.get_width() // 2),
            rect.centery - (label_surface.get_height() // 2),
        ),
    )


def _draw_stat_card(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    value: str,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    pygame.draw.rect(surface, _SECTION_PANEL_ALT_COLOR, rect, border_radius=12)
    pygame.draw.rect(surface, _PANEL_BORDER_COLOR, rect, width=1, border_radius=12)

    label_surface = small_font.render(label.upper(), True, _MUTED_TEXT_COLOR)
    surface.blit(label_surface, (rect.left + 14, rect.top + 12))

    lines = _wrap_text_to_width(value, small_font, rect.width - 28)
    value_font = body_font if len(lines) == 1 and len(value) <= 12 else small_font
    text_rect = pygame.Rect(rect.left + 14, rect.top + 34, rect.width - 28, rect.height - 42)
    _draw_text_block(surface, value, value_font, _TEXT_COLOR, text_rect, line_gap=2)


def _draw_mix_card(
    surface: pygame.Surface,
    rect: pygame.Rect,
    profile,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    pygame.draw.rect(surface, _SECTION_PANEL_ALT_COLOR, rect, border_radius=12)
    pygame.draw.rect(surface, _PANEL_BORDER_COLOR, rect, width=1, border_radius=12)

    heading = small_font.render("CENTER MIX", True, _MUTED_TEXT_COLOR)
    surface.blit(heading, (rect.left + 14, rect.top + 12))

    mix_text = (
        f"Cell {int(profile.center_type_mix.cell_weight * 100)}%  •  "
        f"Edge {int(profile.center_type_mix.edge_weight * 100)}%  •  "
        f"Vertex {int(profile.center_type_mix.vertex_weight * 100)}%"
    )
    mix_rect = pygame.Rect(rect.left + 14, rect.top + 32, rect.width - 28, rect.height - 42)
    _draw_text_block(surface, mix_text, small_font, _SUBTEXT_COLOR, mix_rect, line_gap=2)


def _draw_text_block(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    rect: pygame.Rect,
    *,
    line_gap: int,
) -> None:
    lines = _wrap_text_to_width(text, font, rect.width)
    y = rect.top
    for line in lines:
        line_surface = font.render(line, True, color)
        surface.blit(line_surface, (rect.left, y))
        y += line_surface.get_height() + line_gap


def _draw_centered_text_block(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    rect: pygame.Rect,
    *,
    line_gap: int,
) -> None:
    lines = _wrap_text_to_width(text, font, rect.width)
    y = rect.top
    for line in lines:
        line_surface = font.render(line, True, color)
        line_rect = line_surface.get_rect(center=(rect.centerx, y + (line_surface.get_height() // 2)))
        surface.blit(line_surface, line_rect)
        y += line_surface.get_height() + line_gap


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


def _wrap_text_to_width(
    text: str,
    font: pygame.font.Font,
    max_width: int,
) -> tuple[str, ...]:
    words = text.split()
    if not words:
        return ("",)

    lines: list[str] = []
    current_line = words[0]

    for word in words[1:]:
        candidate = f"{current_line} {word}"
        if font.size(candidate)[0] <= max_width:
            current_line = candidate
            continue
        lines.append(current_line)
        current_line = word

    lines.append(current_line)
    return tuple(lines)


__all__ = [
    "StartScreenHit",
    "StartScreenLayout",
    "StartScreenState",
    "apply_start_screen_hit",
    "build_generation_request_from_state",
    "build_start_screen_layout",
    "default_start_screen_state",
    "difficulty_button_rects",
    "draw_start_screen",
    "generate_puzzle_button_rect",
    "grid_size_button_rects",
    "hit_test_start_screen",
]
