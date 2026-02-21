"""Unit tests for slippage simulation."""

import unittest
from xrpl_router.orderbooks import Level
from xrpl_router.graph import MarketEdge
from xrpl_router.simulate import simulate_path


def _edge(src: str, dst: str, levels: list[tuple[float, float]]) -> MarketEdge:
    return MarketEdge(
        src=src,
        dst=dst,
        levels=[Level(rate=r, capacity=c) for r, c in levels],
    )


class TestSimulate(unittest.TestCase):
    def test_simulate_single_hop(self):
        graph = {
            "A": [_edge("A", "B", [(2.0, 100.0)])],
            "B": [],
        }
        r = simulate_path(["A", "B"], graph, 10.0, fee_fraction=0.0)
        self.assertTrue(r.fully_filled)
        self.assertEqual(r.output_amount, 20.0)
        self.assertEqual(r.effective_rate, 2.0)

    def test_simulate_slippage_two_levels(self):
        graph = {
            "A": [_edge("A", "B", [(2.0, 5.0), (1.0, 100.0)])],
            "B": [],
        }
        r = simulate_path(["A", "B"], graph, 10.0, fee_fraction=0.0)
        self.assertTrue(r.fully_filled)
        self.assertEqual(r.output_amount, 15.0)
        self.assertEqual(r.effective_rate, 1.5)

    def test_simulate_fee(self):
        graph = {
            "A": [_edge("A", "B", [(1.0, 1000.0)])],
            "B": [],
        }
        r = simulate_path(["A", "B"], graph, 100.0, fee_fraction=0.01)
        self.assertTrue(r.fully_filled)
        self.assertEqual(r.output_amount, 99.0)

    def test_simulate_path_three_hop(self):
        graph = {
            "A": [_edge("A", "B", [(2.0, 100.0)])],
            "B": [_edge("B", "C", [(3.0, 100.0)])],
            "C": [],
        }
        r = simulate_path(["A", "B", "C"], graph, 10.0, fee_fraction=0.0)
        self.assertTrue(r.fully_filled)
        self.assertEqual(r.output_amount, 60.0)

    def test_simulate_missing_edge(self):
        graph = {"A": [], "B": []}
        r = simulate_path(["A", "B"], graph, 10.0)
        self.assertFalse(r.fully_filled)
        self.assertEqual(r.output_amount, 0.0)
