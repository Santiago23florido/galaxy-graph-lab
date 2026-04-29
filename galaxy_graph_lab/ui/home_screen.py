from __future__ import annotations

from dataclasses import dataclass

import pygame


_BACKGROUND_COLOR = (18, 17, 26)
_GRID_COLOR = (39, 36, 51)
_OUTER_BORDER_COLOR = (82, 88, 120)
_CARD_COLOR = (34, 31, 41)
_CARD_BORDER_COLOR = (70, 67, 84)
_TEXT_COLOR = (241, 238, 247)
_SUBTEXT_COLOR = (177, 172, 189)
_MUTED_TEXT_COLOR = (119, 115, 132)
_PRIMARY_BUTTON_COLOR = (188, 170, 244)
_PRIMARY_BUTTON_HOVER_COLOR = (203, 188, 250)
_PRIMARY_TEXT_COLOR = (34, 26, 55)
_SECONDARY_BUTTON_COLOR = (44, 41, 54)
_SECONDARY_BUTTON_HOVER_COLOR = (58, 54, 71)
_SECONDARY_BORDER_COLOR = (119, 111, 145)
_GRAPH_LINE_COLOR = (70, 63, 102)
_GRAPH_NODE_COLOR = (92, 85, 124)
_TEXT_PANEL_COLOR = (28, 26, 35)

_DEFAULT_WINDOW_WIDTH = 1280
_DEFAULT_WINDOW_HEIGHT = 820
_MIN_WINDOW_WIDTH = 900
_MIN_WINDOW_HEIGHT = 680

_DETAIL_TEXT = {
    "rules": (
        "Rules",
        (
            "1. Every cell must belong to exactly one galaxy.\n"
            "2. Each galaxy must contain its own center.\n"
            "3. Every galaxy must stay connected.\n"
            "4. Each galaxy must be symmetric under a 180-degree rotation around its center."
        ),
    ),
    "credits": (
        "Credits",
        (
            "Santiago Florido Gomez\n"
            "Mechatronics Engineer\n"
            "EIA University"
        ),
    ),
}


@dataclass(frozen=True, slots=True)
class HomeScreenLayout:
    """Responsive pixel layout for the opening scenes."""

    window_width: int
    window_height: int
    outer_padding: int
    card_width: int
    card_height: int

    @property
    def frame_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.outer_padding,
            self.outer_padding,
            self.window_width - (2 * self.outer_padding),
            self.window_height - (2 * self.outer_padding),
        )

    @property
    def card_rect(self) -> pygame.Rect:
        left = (self.window_width - self.card_width) // 2
        top = (self.window_height - self.card_height) // 2
        return pygame.Rect(left, top, self.card_width, self.card_height)

    @property
    def detail_text_rect(self) -> pygame.Rect:
        card = self.card_rect
        return pygame.Rect(
            card.left + 48,
            card.top + 166,
            card.width - 96,
            card.height - 270,
        )


@dataclass(frozen=True, slots=True)
class HomeScreenHit:
    """One hit-test result for the opening scenes."""

    kind: str


@dataclass(slots=True)
class HomeScreenState:
    """Mutable state shared by the opening scenes."""

    active_panel: str = "rules"


def build_home_screen_layout(
    window_size: tuple[int, int] | None = None,
) -> HomeScreenLayout:
    """Return the responsive layout for the opening scenes."""

    if window_size is None:
        window_width = _DEFAULT_WINDOW_WIDTH
        window_height = _DEFAULT_WINDOW_HEIGHT
    else:
        window_width = max(_MIN_WINDOW_WIDTH, int(window_size[0]))
        window_height = max(_MIN_WINDOW_HEIGHT, int(window_size[1]))

    card_width = min(660, window_width - 180)
    card_height = min(560, window_height - 140)

    return HomeScreenLayout(
        window_width=window_width,
        window_height=window_height,
        outer_padding=8,
        card_width=card_width,
        card_height=card_height,
    )


def default_home_screen_state() -> HomeScreenState:
    """Return the initial opening-scene state."""

    return HomeScreenState()


def start_button_rect(layout: HomeScreenLayout) -> pygame.Rect:
    card = layout.card_rect
    width = min(320, card.width - 160)
    left = card.centerx - (width // 2)
    return pygame.Rect(left, card.top + 270, width, 54)


def rules_button_rect(layout: HomeScreenLayout) -> pygame.Rect:
    card = layout.card_rect
    width = min(320, card.width - 160)
    left = card.centerx - (width // 2)
    return pygame.Rect(left, card.top + 338, width, 48)


def credits_button_rect(layout: HomeScreenLayout) -> pygame.Rect:
    card = layout.card_rect
    width = min(320, card.width - 160)
    left = card.centerx - (width // 2)
    return pygame.Rect(left, card.top + 398, width, 48)


def detail_back_button_rect(layout: HomeScreenLayout) -> pygame.Rect:
    card = layout.card_rect
    width = min(190, card.width - 240)
    left = card.left + 48
    return pygame.Rect(left, card.bottom - 78, width, 46)


def detail_start_button_rect(layout: HomeScreenLayout) -> pygame.Rect:
    card = layout.card_rect
    width = min(190, card.width - 240)
    left = card.right - 48 - width
    return pygame.Rect(left, card.bottom - 78, width, 46)


def hit_test_home_screen(
    layout: HomeScreenLayout,
    pixel_position: tuple[int, int],
) -> HomeScreenHit | None:
    """Return the clicked opening-menu control, if any."""

    if start_button_rect(layout).collidepoint(pixel_position):
        return HomeScreenHit(kind="start")
    if rules_button_rect(layout).collidepoint(pixel_position):
        return HomeScreenHit(kind="rules")
    if credits_button_rect(layout).collidepoint(pixel_position):
        return HomeScreenHit(kind="credits")

    return None


def hit_test_detail_screen(
    layout: HomeScreenLayout,
    pixel_position: tuple[int, int],
) -> HomeScreenHit | None:
    """Return the clicked detail-scene control, if any."""

    if detail_back_button_rect(layout).collidepoint(pixel_position):
        return HomeScreenHit(kind="back")
    if detail_start_button_rect(layout).collidepoint(pixel_position):
        return HomeScreenHit(kind="start")

    return None


def apply_home_screen_hit(
    state: HomeScreenState,
    hit: HomeScreenHit | None,
) -> None:
    """Apply one opening-scene state change."""

    if hit is None:
        return
    if hit.kind in {"rules", "credits"}:
        state.active_panel = hit.kind


def draw_home_screen(
    surface: pygame.Surface,
    layout: HomeScreenLayout,
    hovered_hit: HomeScreenHit | None,
    hero_font: pygame.font.Font,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    """Draw the opening menu before the selection scene."""

    _draw_base_scene(surface, layout)
    _draw_card(surface, layout)
    _draw_home_card_text(surface, layout, hero_font, title_font, body_font, small_font)
    _draw_button(
        surface,
        start_button_rect(layout),
        "Start",
        title_font,
        is_primary=True,
        is_hovered=hovered_hit is not None and hovered_hit.kind == "start",
    )
    _draw_button(
        surface,
        rules_button_rect(layout),
        "Rules",
        body_font,
        is_primary=False,
        is_hovered=hovered_hit is not None and hovered_hit.kind == "rules",
    )
    _draw_button(
        surface,
        credits_button_rect(layout),
        "Credits",
        body_font,
        is_primary=False,
        is_hovered=hovered_hit is not None and hovered_hit.kind == "credits",
    )
    _draw_footer(surface, layout, small_font)


def draw_detail_screen(
    surface: pygame.Surface,
    layout: HomeScreenLayout,
    panel_kind: str,
    hovered_hit: HomeScreenHit | None,
    hero_font: pygame.font.Font,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    """Draw a dedicated Rules or Credits page."""

    if panel_kind not in _DETAIL_TEXT:
        raise ValueError(f"Unknown detail panel: {panel_kind}")

    heading_text, body_text = _DETAIL_TEXT[panel_kind]

    _draw_base_scene(surface, layout)
    _draw_card(surface, layout)

    card = layout.card_rect
    title = hero_font.render(heading_text, True, _TEXT_COLOR)
    title_rect = title.get_rect(center=(card.centerx, card.top + 82))
    surface.blit(title, title_rect)

    subtitle = title_font.render(
        "Review this page, then continue to the puzzle selector.",
        True,
        _SUBTEXT_COLOR,
    )
    subtitle_rect = subtitle.get_rect(center=(card.centerx, title_rect.bottom + 24))
    surface.blit(subtitle, subtitle_rect)

    text_rect = layout.detail_text_rect
    pygame.draw.rect(surface, _TEXT_PANEL_COLOR, text_rect, border_radius=14)
    pygame.draw.rect(surface, _CARD_BORDER_COLOR, text_rect, width=1, border_radius=14)

    wrapped_lines = _wrap_text_lines(body_text, body_font, text_rect.width - 40)
    line_top = text_rect.top + 20
    for index, line in enumerate(wrapped_lines):
        rendered = body_font.render(line, True, _SUBTEXT_COLOR)
        surface.blit(rendered, (text_rect.left + 20, line_top + (index * 34)))

    _draw_button(
        surface,
        detail_back_button_rect(layout),
        "Back",
        body_font,
        is_primary=False,
        is_hovered=hovered_hit is not None and hovered_hit.kind == "back",
    )
    _draw_button(
        surface,
        detail_start_button_rect(layout),
        "Start",
        body_font,
        is_primary=True,
        is_hovered=hovered_hit is not None and hovered_hit.kind == "start",
    )
    _draw_footer(surface, layout, small_font)


def _draw_base_scene(surface: pygame.Surface, layout: HomeScreenLayout) -> None:
    surface.fill(_BACKGROUND_COLOR)
    _draw_grid_background(surface, layout)
    _draw_outer_frame(surface, layout)
    _draw_graph_background(surface, layout)


def _draw_grid_background(surface: pygame.Surface, layout: HomeScreenLayout) -> None:
    for x in range(0, layout.window_width, 40):
        pygame.draw.line(surface, _GRID_COLOR, (x, 0), (x, layout.window_height), 1)
    for y in range(0, layout.window_height, 40):
        pygame.draw.line(surface, _GRID_COLOR, (0, y), (layout.window_width, y), 1)


def _draw_outer_frame(surface: pygame.Surface, layout: HomeScreenLayout) -> None:
    pygame.draw.rect(surface, _OUTER_BORDER_COLOR, layout.frame_rect, width=2, border_radius=16)


def _draw_graph_background(surface: pygame.Surface, layout: HomeScreenLayout) -> None:
    width = layout.window_width
    height = layout.window_height
    points = (
        (width * 0.18, height * 0.40),
        (width * 0.34, height * 0.32),
        (width * 0.58, height * 0.24),
        (width * 0.76, height * 0.51),
        (width * 0.60, height * 0.68),
        (width * 0.38, height * 0.66),
    )
    scaled_points = tuple((int(x), int(y)) for x, y in points)

    for left, right in zip(scaled_points, scaled_points[1:] + scaled_points[:1]):
        pygame.draw.line(surface, _GRAPH_LINE_COLOR, left, right, 2)

    for point in scaled_points:
        pygame.draw.circle(surface, _BACKGROUND_COLOR, point, 5)
        pygame.draw.circle(surface, _GRAPH_NODE_COLOR, point, 5, 2)


def _draw_card(surface: pygame.Surface, layout: HomeScreenLayout) -> None:
    shadow_rect = layout.card_rect.move(0, 10)
    shadow_surface = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(
        shadow_surface,
        (0, 0, 0, 80),
        shadow_surface.get_rect(),
        border_radius=18,
    )
    surface.blit(shadow_surface, shadow_rect.topleft)

    pygame.draw.rect(surface, _CARD_COLOR, layout.card_rect, border_radius=18)
    pygame.draw.rect(surface, _CARD_BORDER_COLOR, layout.card_rect, width=2, border_radius=18)

    dot_y = layout.card_rect.top + 18
    dot_x = layout.card_rect.right - 36
    for offset in (0, 12, 24):
        pygame.draw.circle(surface, _MUTED_TEXT_COLOR, (dot_x + offset, dot_y), 3)


def _draw_home_card_text(
    surface: pygame.Surface,
    layout: HomeScreenLayout,
    hero_font: pygame.font.Font,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    card = layout.card_rect

    title = hero_font.render("Galaxy Graph Lab", True, _TEXT_COLOR)
    title_rect = title.get_rect(center=(card.centerx, card.top + 92))
    surface.blit(title, title_rect)

    subtitle = title_font.render("A graph-based galaxy puzzle lab", True, _SUBTEXT_COLOR)
    subtitle_rect = subtitle.get_rect(center=(card.centerx, title_rect.bottom + 26))
    surface.blit(subtitle, subtitle_rect)

    eyebrow = small_font.render(
        "SYMMETRY  |  CONNECTIVITY  |  STRATEGY  |  PUZZLE GENERATION",
        True,
        _MUTED_TEXT_COLOR,
    )
    eyebrow_rect = eyebrow.get_rect(center=(card.centerx, subtitle_rect.bottom + 28))
    surface.blit(eyebrow, eyebrow_rect)

    hint = body_font.render(
        "Open the puzzle selector or review the dedicated info pages first.",
        True,
        _SUBTEXT_COLOR,
    )
    hint_rect = hint.get_rect(center=(card.centerx, eyebrow_rect.bottom + 28))
    surface.blit(hint, hint_rect)


def _draw_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    is_primary: bool,
    is_hovered: bool,
) -> None:
    if is_primary:
        fill = _PRIMARY_BUTTON_HOVER_COLOR if is_hovered else _PRIMARY_BUTTON_COLOR
        border = fill
        text_color = _PRIMARY_TEXT_COLOR
    else:
        fill = _SECONDARY_BUTTON_HOVER_COLOR if is_hovered else _SECONDARY_BUTTON_COLOR
        border = _SECONDARY_BORDER_COLOR
        text_color = _TEXT_COLOR

    pygame.draw.rect(surface, fill, rect, border_radius=8)
    pygame.draw.rect(surface, border, rect, width=2, border_radius=8)

    text = font.render(label, True, text_color)
    text_rect = text.get_rect(center=rect.center)
    surface.blit(text, text_rect)


def _draw_footer(
    surface: pygame.Surface,
    layout: HomeScreenLayout,
    small_font: pygame.font.Font,
) -> None:
    footer = small_font.render("Created by Santiago Florido Gomez", True, _MUTED_TEXT_COLOR)
    footer_rect = footer.get_rect(center=(layout.window_width // 2, layout.window_height - 44))
    surface.blit(footer, footer_rect)


def _wrap_text_lines(
    text: str,
    font: pygame.font.Font,
    max_width: int,
) -> tuple[str, ...]:
    wrapped_lines: list[str] = []

    for raw_line in text.splitlines():
        if not raw_line.strip():
            wrapped_lines.append("")
            continue

        words = raw_line.split()
        current_line = words[0]

        for word in words[1:]:
            candidate = f"{current_line} {word}"
            if font.size(candidate)[0] <= max_width:
                current_line = candidate
            else:
                wrapped_lines.append(current_line)
                current_line = word

        wrapped_lines.append(current_line)

    return tuple(wrapped_lines)


__all__ = [
    "HomeScreenHit",
    "HomeScreenLayout",
    "HomeScreenState",
    "apply_home_screen_hit",
    "build_home_screen_layout",
    "credits_button_rect",
    "default_home_screen_state",
    "detail_back_button_rect",
    "detail_start_button_rect",
    "draw_detail_screen",
    "draw_home_screen",
    "hit_test_detail_screen",
    "hit_test_home_screen",
    "rules_button_rect",
    "start_button_rect",
]
