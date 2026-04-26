from __future__ import annotations

import pygame

from .puzzle_loader import load_phase_a_puzzle
from .renderer import build_board_layout, draw_phase_a_scene


def run_phase_a_app(max_frames: int | None = None) -> None:
    """Open the first Pygame MVP window and render one fixed puzzle."""

    pygame.init()

    try:
        puzzle = load_phase_a_puzzle()
        layout = build_board_layout(puzzle.puzzle_data)
        surface = pygame.display.set_mode((layout.window_width, layout.window_height))
        pygame.display.set_caption("Galaxy Graph Lab - Phase A")

        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 34)
        body_font = pygame.font.Font(None, 24)
        small_font = pygame.font.Font(None, 21)

        running = True
        frame_count = 0

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            draw_phase_a_scene(
                surface,
                puzzle,
                layout,
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
