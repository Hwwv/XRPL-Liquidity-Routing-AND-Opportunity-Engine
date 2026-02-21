"""Unit tests for arbitrage detection (synthetic negative cycle)."""

import unittest
from xrpl_router.orderbooks import Level
from xrpl_router.graph import MarketEdge
from xrpl_router.arbitrage import scan_arbitrage


def _edge(src: str, dst: str, rate: float, capacity: float = 10000.0) -> MarketEdge:
    return MarketEdge(src=src, dst=dst, levels=[Level(rate=rate, capacity=capacity)])


class TestArbitrage(unittest.TestCase):
    def test_scan_no_arbitrage(self):
        graph = {
            "A": [_edge("A", "B", 1.0)],
            "B": [_edge("B", "C", 1.0)],
            "C": [],
        }
        report = scan_arbitrage(graph, trial_amount=1000.0, fee_fraction=0.0)
        self.assertIsNone(report)

    def test_scan_arbitrage_cycle(self):
        graph = {
            "A": [_edge("A", "B", 2.0)],
            "B": [_edge("B", "C", 2.0)],
            "C": [_edge("C", "A", 0.26)],
        }
        report = scan_arbitrage(graph, trial_amount=1000.0, fee_fraction=0.0)
        self.assertIsNotNone(report)
        self.assertGreaterEqual(len(report.cycle), 2)
        self.assertGreater(report.profit_absolute, 0)
        self.assertGreater(report.confidence, 0)
