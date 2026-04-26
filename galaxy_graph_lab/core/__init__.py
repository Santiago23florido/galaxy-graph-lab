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
from .solver_service import (
    DEFAULT_SOLVER_BACKEND,
    PuzzleSolveResult,
    SOLVER_STATUS_BACKEND_UNAVAILABLE,
    SOLVER_STATUS_ERROR,
    SOLVER_STATUS_INFEASIBLE,
    SOLVER_STATUS_SOLVED,
    SOLVER_STATUS_UNSUPPORTED_BACKEND,
    solve_puzzle,
)
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
    "DEFAULT_SOLVER_BACKEND",
    "BaseMilpModel",
    "BaseMilpSolveResult",
    "DirectedFlowKey",
    "FlowMilpModel",
    "FlowMilpSolveResult",
    "GalaxyAssignment",
    "PuzzleSolveResult",
    "SOLVER_STATUS_BACKEND_UNAVAILABLE",
    "SOLVER_STATUS_ERROR",
    "SOLVER_STATUS_INFEASIBLE",
    "SOLVER_STATUS_SOLVED",
    "SOLVER_STATUS_UNSUPPORTED_BACKEND",
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
    "solve_puzzle",
    "solve_base_model",
    "solve_flow_model",
]
