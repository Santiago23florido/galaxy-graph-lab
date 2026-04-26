from __future__ import annotations

import pygame

from .puzzle_loader import load_phase_a_puzzle
from .renderer import build_board_layout, draw_phase_a_scene, hit_test_board_geometry


def run_phase_b_app(max_frames: int | None = None) -> None:
    """Open the Phase B Pygame window with clickable board geometry."""

    pygame.init()

    try:
        puzzle = load_phase_a_puzzle()
        layout = build_board_layout(puzzle.puzzle_data)
        surface = pygame.display.set_mode((layout.window_width, layout.window_height))
        pygame.display.set_caption("Galaxy Graph Lab - Phase B")

        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 34)
        body_font = pygame.font.Font(None, 24)
        small_font = pygame.font.Font(None, 21)

        running = True
        frame_count = 0
        hovered_hit = None
        selected_hit = None

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.MOUSEMOTION:
                    hovered_hit = hit_test_board_geometry(
                        puzzle.puzzle_data,
                        layout,
                        event.pos,
                    )
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    selected_hit = hit_test_board_geometry(
                        puzzle.puzzle_data,
                        layout,
                        event.pos,
                    )

            draw_phase_a_scene(
                surface,
                puzzle,
                layout,
                hovered_hit=hovered_hit,
                selected_hit=selected_hit,
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


def run_phase_a_app(max_frames: int | None = None) -> None:
    """Compatibility wrapper for the previous Phase A entrypoint name."""

    run_phase_b_app(max_frames=max_frames)
