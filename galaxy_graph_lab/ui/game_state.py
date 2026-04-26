from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ..core import Cell
from .renderer import GeometryHit


@dataclass(slots=True)
class EditablePuzzleState:
    """Mutable Phase C state for tentative center-to-cell assignments."""

    center_ids: tuple[str, ...]
    selected_center_id: str | None = None
    last_hit: GeometryHit | None = None
    _assigned_center_by_cell: dict[Cell, str] = field(default_factory=dict)

    @classmethod
    def from_center_ids(cls, center_ids: tuple[str, ...]) -> "EditablePuzzleState":
        return cls(center_ids=center_ids)

    @property
    def assigned_center_by_cell(self) -> Mapping[Cell, str]:
        return MappingProxyType(dict(self._assigned_center_by_cell))

    def assigned_center_for_cell(self, cell: Cell) -> str | None:
        return self._assigned_center_by_cell.get(cell)

    def center_counts(self) -> Mapping[str, int]:
        counts = {center_id: 0 for center_id in self.center_ids}
        for center_id in self._assigned_center_by_cell.values():
            counts[center_id] += 1
        return MappingProxyType(counts)

    def apply_left_click(self, hit: GeometryHit | None) -> None:
        """Apply one Phase C interaction using the current left-click policy."""

        self.last_hit = hit
        if hit is None:
            return

        if hit.kind == "center" and hit.center_id is not None:
            self.selected_center_id = hit.center_id
            return

        if hit.kind != "cell" or hit.cell is None or self.selected_center_id is None:
            return

        current_owner = self._assigned_center_by_cell.get(hit.cell)
        if current_owner == self.selected_center_id:
            del self._assigned_center_by_cell[hit.cell]
            return

        self._assigned_center_by_cell[hit.cell] = self.selected_center_id

    def reset_assignments(self) -> None:
        self._assigned_center_by_cell.clear()
        self.last_hit = None

