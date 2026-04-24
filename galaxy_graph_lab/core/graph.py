from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from types import MappingProxyType

from .board import BoardSpec, Cell


GridEdge = tuple[Cell, Cell]

_ORTHOGONAL_OFFSETS = ((-1, 0), (0, -1), (0, 1), (1, 0))


class GridGraph:
    """Unweighted undirected grid graph H = (U, E)."""

    def __init__(self, board: BoardSpec) -> None:
        self.board = board
        self.cells = board.cells()
        self._cell_set = set(self.cells)
        self._index_by_cell = {cell: index for index, cell in enumerate(self.cells)}
        self._neighbors = MappingProxyType(self._build_neighbors())
        self.edges = self._build_edges()

    def _build_neighbors(self) -> dict[Cell, tuple[Cell, ...]]:
        neighbors: dict[Cell, tuple[Cell, ...]] = {}

        for cell in self.cells:
            neighbors[cell] = self._orthogonal_neighbors(cell)

        return neighbors

    def _build_edges(self) -> tuple[GridEdge, ...]:
        edges: list[GridEdge] = []

        for cell in self.cells:
            for neighbor in self.neighbors(cell):
                if cell < neighbor:
                    edges.append((cell, neighbor))

        return tuple(edges)

    def _orthogonal_neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        neighbors: list[Cell] = []

        for row_delta, col_delta in _ORTHOGONAL_OFFSETS:
            row = cell.row + row_delta
            col = cell.col + col_delta
            if self.board.contains_indices(row, col):
                neighbors.append(Cell(row=row, col=col))

        return tuple(neighbors)

    def _require_cell(self, cell: Cell) -> None:
        if cell not in self._cell_set:
            raise ValueError(f"Cell is not in the graph: {cell}")

    def _require_cells(self, cells: set[Cell]) -> None:
        unknown_cells = cells.difference(self._cell_set)
        if unknown_cells:
            first_cell = min(unknown_cells)
            raise ValueError(f"Cell is not in the graph: {first_cell}")

    def index_of(self, cell: Cell) -> int:
        """Return the canonical index of a board cell."""

        self._require_cell(cell)
        return self._index_by_cell[cell]

    def neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        """Return side-neighbors for one board cell."""

        self._require_cell(cell)
        return self._neighbors[cell]

    def neighbor_map(self) -> Mapping[Cell, tuple[Cell, ...]]:
        """Return the read-only full adjacency map."""

        return self._neighbors

    def induced_neighbors(
        self,
        cells: Iterable[Cell],
        cell: Cell,
    ) -> tuple[Cell, ...]:
        """Return neighbors that stay inside the chosen cell set."""

        self._require_cell(cell)
        allowed_cells = set(cells)
        self._require_cells(allowed_cells)

        if cell not in allowed_cells:
            return ()

        return tuple(
            neighbor for neighbor in self.neighbors(cell) if neighbor in allowed_cells
        )

    def traverse_component(
        self,
        cells: Iterable[Cell],
        start: Cell,
    ) -> tuple[Cell, ...]:
        """Traverse one connected component in the induced grid."""

        allowed_cells = set(cells)
        self._require_cells(allowed_cells)
        self._require_cell(start)

        if start not in allowed_cells:
            raise ValueError("Start cell must belong to the induced cell set.")

        visited = {start}
        queue: deque[Cell] = deque([start])
        component: list[Cell] = []

        while queue:
            cell = queue.popleft()
            component.append(cell)

            for neighbor in self.neighbors(cell):
                if neighbor in allowed_cells and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return tuple(component)

    def connected_components(
        self,
        cells: Iterable[Cell],
    ) -> tuple[tuple[Cell, ...], ...]:
        """Return all connected components in the induced grid."""

        allowed_cells = set(cells)
        self._require_cells(allowed_cells)

        remaining = set(allowed_cells)
        components: list[tuple[Cell, ...]] = []

        while remaining:
            start = min(remaining)
            component = self.traverse_component(allowed_cells, start)
            components.append(component)
            remaining.difference_update(component)

        return tuple(components)

    def is_connected(self, cells: Iterable[Cell]) -> bool:
        """Return whether the chosen cells form one connected component."""

        return len(self.connected_components(cells)) == 1


__all__ = ["GridEdge", "GridGraph"]
