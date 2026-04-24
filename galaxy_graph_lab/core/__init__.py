"""Core exports for the solver-agnostic Galaxy layer."""

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
from .validators import (
    AssignmentValidationResult,
    CandidateAssignment,
    admissibility_is_valid,
    connectivity_is_valid,
    kernel_is_valid,
    partition_is_valid,
    symmetry_is_valid,
    validate_assignment,
)

__all__ = [
    "BoardSpec",
    "Cell",
    "CenterSpec",
    "GridEdge",
    "GridGraph",
    "PuzzleData",
    "AssignmentValidationResult",
    "CandidateAssignment",
    "admissible_cells",
    "admissibility_is_valid",
    "connectivity_is_valid",
    "is_admissible_cell",
    "is_kernel_cell",
    "kernel_is_valid",
    "kernel_cells",
    "partition_is_valid",
    "symmetry_is_valid",
    "tau",
    "twin_cell",
    "twin_map",
    "validate_assignment",
]
