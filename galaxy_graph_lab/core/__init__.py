"""Core exports for the Galaxy geometry layer."""

from .board import BoardSpec, Cell
from .centers import CenterSpec
from .geometry import (
    admissible_cells,
    is_admissible_cell,
    is_kernel_cell,
    kernel_cells,
    tau,
    twin_cell,
    twin_map,
)
from .graph import GridEdge, GridGraph
from .model_data import PuzzleData

__all__ = [
    "BoardSpec",
    "Cell",
    "CenterSpec",
    "GridEdge",
    "GridGraph",
    "PuzzleData",
    "admissible_cells",
    "is_admissible_cell",
    "is_kernel_cell",
    "kernel_cells",
    "tau",
    "twin_cell",
    "twin_map",
]
