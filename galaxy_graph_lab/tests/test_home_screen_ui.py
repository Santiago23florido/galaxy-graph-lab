from __future__ import annotations

import unittest

from galaxy_graph_lab.ui.home_screen import (
    apply_home_screen_hit,
    build_home_screen_layout,
    credits_button_rect,
    detail_back_button_rect,
    detail_start_button_rect,
    default_home_screen_state,
    hit_test_detail_screen,
    hit_test_home_screen,
    rules_button_rect,
    start_button_rect,
)


class HomeScreenUiTests(unittest.TestCase):
    def test_default_home_screen_state_shows_rules(self) -> None:
        state = default_home_screen_state()

        self.assertEqual(state.active_panel, "rules")

    def test_layout_uses_requested_window_size(self) -> None:
        layout = build_home_screen_layout((1500, 940))

        self.assertEqual(layout.window_width, 1500)
        self.assertEqual(layout.window_height, 940)

    def test_hit_testing_identifies_home_controls(self) -> None:
        layout = build_home_screen_layout()

        start_hit = hit_test_home_screen(layout, start_button_rect(layout).center)
        rules_hit = hit_test_home_screen(layout, rules_button_rect(layout).center)
        credits_hit = hit_test_home_screen(layout, credits_button_rect(layout).center)

        self.assertIsNotNone(start_hit)
        self.assertEqual(start_hit.kind, "start")
        self.assertIsNotNone(rules_hit)
        self.assertEqual(rules_hit.kind, "rules")
        self.assertIsNotNone(credits_hit)
        self.assertEqual(credits_hit.kind, "credits")

    def test_apply_home_screen_hit_switches_info_panel(self) -> None:
        layout = build_home_screen_layout()
        state = default_home_screen_state()

        apply_home_screen_hit(
            state,
            hit_test_home_screen(layout, credits_button_rect(layout).center),
        )

        self.assertEqual(state.active_panel, "credits")

    def test_hit_testing_identifies_detail_controls(self) -> None:
        layout = build_home_screen_layout()

        back_hit = hit_test_detail_screen(layout, detail_back_button_rect(layout).center)
        start_hit = hit_test_detail_screen(layout, detail_start_button_rect(layout).center)

        self.assertIsNotNone(back_hit)
        self.assertEqual(back_hit.kind, "back")
        self.assertIsNotNone(start_hit)
        self.assertEqual(start_hit.kind, "start")


if __name__ == "__main__":
    unittest.main()
