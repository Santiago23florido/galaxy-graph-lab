"""Smoke tests for the initial project setup."""

from __future__ import annotations

from galaxy_graph_lab import __version__
from galaxy_graph_lab.main import build_status_report


def test_package_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_status_report_mentions_python_and_pygame() -> None:
    report = build_status_report()

    assert "Python:" in report
    assert "Pygame:" in report
    assert "environment is ready" in report
