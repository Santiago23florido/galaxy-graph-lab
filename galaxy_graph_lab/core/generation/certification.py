from __future__ import annotations

from dataclasses import dataclass

from ..model_data import PuzzleData
from ..solver_service import PuzzleSolveResult, solve_puzzle
from ..validators import AssignmentValidationResult, CandidateAssignment, validate_assignment


@dataclass(frozen=True, slots=True)
class PuzzleCertificationResult:
    """Structured certification report for one generated puzzle candidate."""

    success: bool
    message: str
    constructive_validation: AssignmentValidationResult
    solve_result: PuzzleSolveResult
    certified_validation: AssignmentValidationResult | None


def certify_generated_puzzle(
    puzzle_data: PuzzleData,
    constructive_assignment: CandidateAssignment,
) -> PuzzleCertificationResult:
    """Validate the constructive assignment and certify the puzzle with the solver."""

    constructive_validation = validate_assignment(puzzle_data, constructive_assignment)
    if not constructive_validation.is_valid:
        return PuzzleCertificationResult(
            success=False,
            message="Constructive assignment failed structural validation.",
            constructive_validation=constructive_validation,
            solve_result=PuzzleSolveResult(
                success=False,
                backend_name="exact_flow",
                status_code=-4,
                status_label="generation_error",
                message="Constructive assignment failed structural validation.",
                assignment=None,
                objective_value=None,
                mip_gap=None,
                mip_node_count=None,
            ),
            certified_validation=None,
        )

    solve_result = solve_puzzle(puzzle_data)
    if not solve_result.success or solve_result.assignment is None:
        return PuzzleCertificationResult(
            success=False,
            message=solve_result.message,
            constructive_validation=constructive_validation,
            solve_result=solve_result,
            certified_validation=None,
        )

    certified_validation = validate_assignment(
        puzzle_data,
        solve_result.assignment.cells_by_center,
    )
    if not certified_validation.is_valid:
        return PuzzleCertificationResult(
            success=False,
            message="Solver returned an assignment that failed structural validation.",
            constructive_validation=constructive_validation,
            solve_result=solve_result,
            certified_validation=certified_validation,
        )

    return PuzzleCertificationResult(
        success=True,
        message="Puzzle generated successfully.",
        constructive_validation=constructive_validation,
        solve_result=solve_result,
        certified_validation=certified_validation,
    )


__all__ = ["PuzzleCertificationResult", "certify_generated_puzzle"]
