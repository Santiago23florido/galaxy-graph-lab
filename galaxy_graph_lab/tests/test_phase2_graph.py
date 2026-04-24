from __future__ import annotations

import unittest

from core import BoardSpec, Cell, CenterSpec, GridGraph, PuzzleData


class Phase2GraphTests(unittest.TestCase):
    def test_neighbors_are_orthogonal_and_inside_board(self) -> None:
        graph = GridGraph(BoardSpec(rows=3, cols=3))

        self.assertEqual(
            graph.neighbors(Cell(0, 0)),
            (Cell(0, 1), Cell(1, 0)),
        )
        self.assertEqual(
            graph.neighbors(Cell(1, 1)),
            (Cell(0, 1), Cell(1, 0), Cell(1, 2), Cell(2, 1)),
        )

    def test_grid_edges_are_undirected_and_unweighted(self) -> None:
        graph = GridGraph(BoardSpec(rows=2, cols=3))

        self.assertEqual(len(graph.edges), 7)
        self.assertEqual(len(set(graph.edges)), 7)
        self.assertTrue(all(left < right for left, right in graph.edges))
        self.assertEqual(graph.edges[0], (Cell(0, 0), Cell(0, 1)))

    def test_index_of_uses_canonical_cell_order(self) -> None:
        graph = GridGraph(BoardSpec(rows=2, cols=3))

        self.assertEqual(graph.index_of(Cell(0, 0)), 0)
        self.assertEqual(graph.index_of(Cell(0, 2)), 2)
        self.assertEqual(graph.index_of(Cell(1, 0)), 3)

    def test_induced_neighbors_filter_outside_cells(self) -> None:
        graph = GridGraph(BoardSpec(rows=3, cols=3))
        cells = {Cell(0, 0), Cell(0, 1), Cell(1, 1)}

        self.assertEqual(
            graph.induced_neighbors(cells, Cell(0, 1)),
            (Cell(0, 0), Cell(1, 1)),
        )

    def test_traverse_component(self) -> None:
        graph = GridGraph(BoardSpec(rows=3, cols=3))
        cells = {Cell(0, 0), Cell(0, 1), Cell(2, 2)}

        self.assertEqual(
            graph.traverse_component(cells, Cell(0, 0)),
            (Cell(0, 0), Cell(0, 1)),
        )

    def test_connected_components_and_connectivity(self) -> None:
        graph = GridGraph(BoardSpec(rows=3, cols=3))
        disconnected = {Cell(0, 0), Cell(0, 1), Cell(2, 2)}
        connected = {Cell(0, 0), Cell(0, 1), Cell(1, 1)}

        self.assertEqual(
            graph.connected_components(disconnected),
            ((Cell(0, 0), Cell(0, 1)), (Cell(2, 2),)),
        )
        self.assertFalse(graph.is_connected(disconnected))
        self.assertTrue(graph.is_connected(connected))
        self.assertFalse(graph.is_connected(set()))

    def test_puzzle_data_precomputes_grid_graph_and_neighbors(self) -> None:
        board = BoardSpec(rows=2, cols=2)
        center = CenterSpec.from_coordinates("g0", 0, 0)
        puzzle_data = PuzzleData.from_specs(board, [center])

        self.assertIsInstance(puzzle_data.graph, GridGraph)
        self.assertEqual(
            puzzle_data.neighbors[Cell(0, 0)],
            (Cell(0, 1), Cell(1, 0)),
        )
        self.assertTrue(puzzle_data.graph.is_connected({Cell(0, 0), Cell(0, 1)}))


if __name__ == "__main__":
    unittest.main()
