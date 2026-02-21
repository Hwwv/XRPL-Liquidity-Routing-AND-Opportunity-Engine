"""
Full-stack tests using mock data only (no network).
Covers route, arbitrage, simulate end-to-end with deterministic mock graph.
"""
import unittest
from xrpl_router.config import DEFAULT_ISSUER
from xrpl_router.loader import get_graph
from xrpl_router.mock_data import get_mock_graph, get_mock_graph_with_arbitrage
from xrpl_router.routing import dijkstra_best_path, bellman_ford_negative_cycle
from xrpl_router.simulate import simulate_path
from xrpl_router.arbitrage import scan_arbitrage
from xrpl_router.strategy import evaluate_routes, greedy_agent_step


def _resolve(asset: str) -> str:
    if asset.upper() == "XRP":
        return "XRP"
    if ":" in asset:
        return asset
    return f"{asset.upper()}:{DEFAULT_ISSUER}"


class TestMockIntegration(unittest.TestCase):
    """Run full pipeline with get_mock_graph()."""

    def test_mock_graph_builds(self):
        graph = get_graph(use_mock=True)
        self.assertIsInstance(graph, dict)
        self.assertIn("XRP", graph)
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
        report = scan_arbitrage(graph, trial_amount=1000.0)
        self.assertIsNotNone(report)
        self.assertGreater(len(report.cycle), 1)
        self.assertGreater(report.profit_absolute, 0)

    def test_simulate_mock(self):
        graph = get_graph(use_mock=True)
        portfolio = {"XRP": 100.0}
        choice, used = greedy_agent_step(graph, portfolio)
        self.assertIsNotNone(choice)
        self.assertEqual(used, "XRP")
        self.assertGreater(choice.output_amount, 0)

    def test_evaluate_routes_mock(self):
        graph = get_graph(use_mock=True)
        choice = evaluate_routes(graph, "XRP", 100.0)
        self.assertIsNotNone(choice)
        self.assertGreaterEqual(len(choice.path), 2)
