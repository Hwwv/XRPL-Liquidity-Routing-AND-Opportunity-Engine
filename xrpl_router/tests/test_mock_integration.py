"""
Full-stack tests using mock data only (no network).
Covers route, arbitrage, simulate end-to-end with deterministic mock graph.
"""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from xrpl_router.config import DEFAULT_ISSUER
from xrpl_router.loader import get_graph
from xrpl_router.mock_data import (
    get_mock_graph,
    get_mock_graph_divergence,
    get_mock_graph_with_arbitrage,
)
from xrpl_router.routing import dijkstra_best_path, bellman_ford_negative_cycle
from xrpl_router.simulate import simulate_path
from xrpl_router.arbitrage import scan_arbitrage
from xrpl_router.strategy import AgentState, evaluate_routes, greedy_agent_step
from xrpl_router.graph import Asset


def _resolve(asset: str) -> Asset:
    if asset.upper() == "XRP":
        return Asset("XRP", None)
    if ":" in asset:
        return Asset(asset.split(":", 1)[0].upper(), asset.split(":", 1)[1] or None)
    return Asset(asset.upper(), DEFAULT_ISSUER)


class TestMockIntegration(unittest.TestCase):
    """Run full pipeline with get_mock_graph()."""

    def test_mock_graph_builds(self):
        graph = get_graph(use_mock=True)
        self.assertIsInstance(graph, dict)
        self.assertIn(Asset("XRP", None), graph)
        self.assertGreater(len(graph), 0)

    def test_divergence_mock_graph_builds(self):
        graph = get_mock_graph_divergence()
        self.assertIsInstance(graph, dict)
        self.assertIn(Asset("XRP", None), graph)
        self.assertGreater(len(graph), 0)

    def test_route_mock(self):
        graph = get_graph(use_mock=True)
        source = _resolve("XRP")
        target = _resolve("USD")
        result = dijkstra_best_path(graph, source, target)
        self.assertIsNotNone(result)
        self.assertEqual(result.path[0], source)
        self.assertEqual(result.path[-1], target)
        sim = simulate_path(result.path, graph, 100.0)
        self.assertTrue(sim.output_amount > 0)
        self.assertTrue(sim.effective_rate > 0)

    def test_arbitrage_mock_no_cycle(self):
        graph = get_graph(use_mock=True)
        report = scan_arbitrage(graph, trial_amount=1000.0)
        # Default mock has no negative cycle
        self.assertIsNone(report)

    def test_arbitrage_mock_with_cycle(self):
        graph = get_mock_graph_with_arbitrage()
        report = scan_arbitrage(graph, trial_amount=1000.0, fee_fraction=0.0)
        self.assertIsNotNone(report)
        self.assertGreater(len(report.cycle), 1)
        self.assertGreater(report.profit_absolute, 0)

    def test_simulate_mock(self):
        graph = get_graph(use_mock=True)
        portfolio = {Asset("XRP", None): 100.0}
        state = AgentState()
        choice, used = greedy_agent_step(graph, portfolio, step=0, state=state)
        if choice is None:
            self.assertEqual(used, "")
        else:
            self.assertEqual(used, Asset("XRP", None))
            self.assertGreater(choice.output_amount, 0)

    def test_evaluate_routes_mock(self):
        graph = get_graph(use_mock=True)
        choice = evaluate_routes(graph, Asset("XRP", None), 100.0)
        self.assertIsNotNone(choice)
        self.assertGreaterEqual(len(choice.path), 1)


if __name__ == "__main__":
    unittest.main()
