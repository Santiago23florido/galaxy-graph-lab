"""Smoke entrypoint for verifying the initial project setup."""

from __future__ import annotations

import sys

import pygame


def build_status_report() -> str:
    """Return a short setup report for the local environment."""
    return "\n".join(
        [
            "Galaxy Graph Lab setup check",
            f"Python: {sys.version.split()[0]}",
            f"Pygame: {pygame.version.ver}",
            "Status: environment is ready.",
        ]
    )


def main() -> None:
    """Print the setup report."""
    print(build_status_report())


if __name__ == "__main__":
    main()
