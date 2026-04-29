from __future__ import annotations

from dataclasses import dataclass

import pygame

from ..core import BoardSpec, PuzzleGenerationRequest, difficulty_profile_for, difficulty_profiles


_BACKGROUND_COLOR = (24, 29, 36)
_PANEL_COLOR = (35, 43, 52)
_TEXT_COLOR = (233, 238, 243)
_SUBTEXT_COLOR = (172, 180, 190)
_BUTTON_COLOR = (61, 193, 211)
_BUTTON_HOVER_COLOR = (82, 215, 232)
_BUTTON_IDLE_COLOR = (52, 61, 72)
_BUTTON_IDLE_HOVER_COLOR = (66, 76, 88)
_BUTTON_SELECTED_COLOR = (88, 191, 116)
_BUTTON_SELECTED_HOVER_COLOR = (104, 205, 131)
_BUTTON_TEXT_COLOR = (15, 17, 20)
_BUTTON_IDLE_TEXT_COLOR = (233, 238, 243)
_BORDER_COLOR = (15, 17, 20)


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


def build_start_screen_layout() -> StartScreenLayout:
    """Return the fixed layout for the start screen scene."""

    return StartScreenLayout(
        window_width=980,
        window_height=720,
        padding=24,
        panel_width=860,
        panel_height=620,
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
    panel = layout.panel_rect
    top = panel.top + 190
    left = panel.left + 48
    width = 220
    height = 52
    gap = 20

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
    panel = layout.panel_rect
    top = panel.top + 360
    left = panel.left + 48
    width = 180
    height = 52
    gap = 18

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
        panel.top + 548,
        panel.width - 96,
        58,
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

    surface.fill(_BACKGROUND_COLOR)
    pygame.draw.rect(surface, _PANEL_COLOR, layout.panel_rect, border_radius=16)

    panel = layout.panel_rect
    left = panel.left + 48
    top = panel.top + 42

    title = title_font.render("Galaxy Graph Lab", True, _TEXT_COLOR)
    subtitle = body_font.render("Choose a difficulty and grid size before generating a puzzle.", True, _SUBTEXT_COLOR)
    surface.blit(title, (left, top))
    surface.blit(subtitle, (left, top + title.get_height() + 14))

    difficulty_heading = body_font.render("Difficulty", True, _TEXT_COLOR)
    surface.blit(difficulty_heading, (left, panel.top + 145))

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

    grid_heading = body_font.render("Grid Size", True, _TEXT_COLOR)
    surface.blit(grid_heading, (left, panel.top + 315))

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
    profile_lines = (
        f"Allowed sizes: {', '.join(f'{size.rows}x{size.cols}' for size in profile.allowed_grid_sizes)}",
        f"Centers: {profile.min_center_count} to {profile.max_center_count}",
        (
            "Center mix: "
            f"cell {int(profile.center_type_mix.cell_weight * 100)}% | "
            f"edge {int(profile.center_type_mix.edge_weight * 100)}% | "
            f"vertex {int(profile.center_type_mix.vertex_weight * 100)}%"
        ),
        (
            "Overlap target: "
            f"{int(profile.overlap_target_range.min_ratio * 100)}% to "
            f"{int(profile.overlap_target_range.max_ratio * 100)}%"
        ),
        f"Uniqueness required: {'Yes' if profile.uniqueness_required else 'No'}",
    )
    profile_top = panel.top + 440
    for index, line in enumerate(profile_lines):
        text = small_font.render(line, True, _SUBTEXT_COLOR)
        surface.blit(text, (left, profile_top + (index * 24)))

    generate_rect = generate_puzzle_button_rect(layout)
    is_generate_hovered = hovered_hit is not None and hovered_hit.kind == "generate"
    _draw_primary_button(
        surface,
        generate_rect,
        "Generate Puzzle",
        body_font,
        is_hovered=is_generate_hovered,
    )

    message_lines = _wrap_text(state.status_message, 80)
    message_top = generate_rect.bottom + 14
    for index, line in enumerate(message_lines):
        message = small_font.render(line, True, _SUBTEXT_COLOR)
        surface.blit(message, (left, message_top + (index * 22)))


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
    pygame.draw.rect(surface, _BORDER_COLOR, rect, width=2, border_radius=10)
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
    pygame.draw.rect(surface, _BORDER_COLOR, rect, width=2, border_radius=10)
    label_surface = font.render(label, True, _BUTTON_TEXT_COLOR)
    surface.blit(
        label_surface,
        (
            rect.centerx - (label_surface.get_width() // 2),
            rect.centery - (label_surface.get_height() // 2),
        ),
    )


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
