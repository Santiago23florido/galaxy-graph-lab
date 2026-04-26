"""Core exports for the Galaxy mathematical and solver layers."""

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
from .milp import (
    BaseMilpModel,
    BaseMilpSolveResult,
    DirectedFlowKey,
    FlowMilpModel,
    FlowMilpSolveResult,
    GalaxyAssignment,
    SourceFlowKey,
    solve_base_model,
    solve_flow_model,
)
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
    "BaseMilpModel",
    "BaseMilpSolveResult",
    "DirectedFlowKey",
    "FlowMilpModel",
    "FlowMilpSolveResult",
    "GalaxyAssignment",
    "SourceFlowKey",
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
    "solve_base_model",
    "solve_flow_model",
]
