from .certification import PuzzleCertificationResult, certify_generated_puzzle
from .center_placement import (
    CenterPlacementResult,
    PlacedCenterRegion,
    RectangleRegion,
    place_candidate_centers,
    sample_target_center_count,
)
from .difficulty import (
    DifficultyCalibration,
    calibrate_generated_puzzle_difficulty,
    region_irregularity,
)
from .partition_closure import PartitionClosureResult, close_candidate_partition
from .preference_shaping import build_preferred_assignment_by_cell
from .profiles import (
    CENTER_TYPE_CELL,
    CENTER_TYPE_EDGE,
    CENTER_TYPE_VERTEX,
    CENTER_TYPES,
    CenterTypeMix,
    DifficultyProfile,
    OverlapTargetRange,
    difficulty_profile_for,
    difficulty_profiles,
)
from .request import (
    GENERATION_DIFFICULTIES,
    GENERATION_DIFFICULTY_EASY,
    GENERATION_DIFFICULTY_HARD,
    GENERATION_DIFFICULTY_MEDIUM,
    PuzzleGenerationRequest,
)
from .region_growth import grow_candidate_regions
from .service import (
    GENERATION_STATUS_ERROR,
    GENERATION_STATUS_GENERATED,
    GeneratedPuzzle,
    PuzzleGenerationResult,
    generate_puzzle,
)

__all__ = [
    "CENTER_TYPE_CELL",
    "CENTER_TYPE_EDGE",
    "CENTER_TYPE_VERTEX",
    "CENTER_TYPES",
    "CenterPlacementResult",
    "CenterTypeMix",
    "DifficultyCalibration",
    "DifficultyProfile",
    "GENERATION_DIFFICULTIES",
    "GENERATION_DIFFICULTY_EASY",
    "GENERATION_DIFFICULTY_HARD",
    "GENERATION_DIFFICULTY_MEDIUM",
    "GENERATION_STATUS_ERROR",
    "GENERATION_STATUS_GENERATED",
    "GeneratedPuzzle",
    "OverlapTargetRange",
    "PartitionClosureResult",
    "PlacedCenterRegion",
    "PuzzleCertificationResult",
    "PuzzleGenerationRequest",
    "PuzzleGenerationResult",
    "RectangleRegion",
    "build_preferred_assignment_by_cell",
    "calibrate_generated_puzzle_difficulty",
    "certify_generated_puzzle",
    "close_candidate_partition",
    "difficulty_profile_for",
    "difficulty_profiles",
    "grow_candidate_regions",
    "generate_puzzle",
    "place_candidate_centers",
    "region_irregularity",
    "sample_target_center_count",
]
