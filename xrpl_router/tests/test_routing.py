"""Unit tests for routing (Dijkstra, Bellman-Ford) with synthetic graphs."""
import unittest
from xrpl_router.orderbooks import Level
from xrpl_router.graph import MarketEdge
from xrpl_router.routing import dijkstra_best_path, bellman_ford_negative_cycle, _weight


def _edge(src: str, dst: str, rate: float, capacity: float = 1000.0) -> MarketEdge:
    return MarketEdge(src=src, dst=dst, levels=[Level(rate=rate, capacity=capacity)])


class TestRouting(unittest.TestCase):
    def test_dijkstra_simple_path(self):
        graph = {
            "A": [_edge("A", "B", 2.0), _edge("A", "C", 1.0)],
            "B": [_edge("B", "C", 1.0)],
            "C": [],
        }
        result = dijkstra_best_path(graph, "A", "C")
        self.assertIsNotNone(result)
        self.assertEqual(result.path, ["A", "B", "C"])
        self.assertEqual(result.effective_rate, 2.0)

    def test_dijkstra_no_path(self):
        graph = {"A": [_edge("A", "B", 1.0)], "B": []}
        result = dijkstra_best_path(graph, "A", "C")
        self.assertIsNone(result)

    def test_dijkstra_same_source_target(self):
        graph = {"A": [_edge("A", "B", 1.0)], "B": []}
        result = dijkstra_best_path(graph, "A", "A")
        self.assertIsNotNone(result)
        self.assertEqual(result.path, ["A"])
        self.assertEqual(result.effective_rate, 1.0)

    def test_weight(self):
        self.assertEqual(_weight(1.0), 0.0)
        self.assertLess(_weight(2.0), 0)
        self.assertGreater(_weight(0.5), 0)

    def test_bellman_ford_no_cycle(self):
        graph = {
            "A": [_edge("A", "B", 1.0)],
            "B": [_edge("B", "C", 1.0)],
            "C": [],
        }
        cycle = bellman_ford_negative_cycle(graph)
        self.assertIsNone(cycle)

    def test_bellman_ford_negative_cycle(self):
        # Product 2*2*0.26 = 1.04 > 1 => -log(1.04) < 0 => negative cycle
        graph = {
            "A": [_edge("A", "B", 2.0)],
            "B": [_edge("B", "C", 2.0)],
            "C": [_edge("C", "A", 0.26)],
        }
        cycle = bellman_ford_negative_cycle(graph)
        self.assertIsNotNone(cycle)
        self.assertGreaterEqual(len(cycle), 2)
        self.assertEqual(cycle[0], cycle[-1])
        self.assertLessEqual(set(cycle), {"A", "B", "C"})
