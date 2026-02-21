"""
Tests for base-asset scoring and cooldown/reversal protection.
"""

import unittest
from types import SimpleNamespace

from xrpl_router import config as cfg
from xrpl_router.graph import Asset, MarketEdge
from xrpl_router.mock_data import get_mock_graph
from xrpl_router.orderbooks import Level
from xrpl_router.strategy import AgentState, greedy_agent_step
from xrpl_router.valuation import value_in_base


class TestChurnPrevention(unittest.TestCase):
    def test_long_run_mock_does_not_collapse(self):
        graph = get_mock_graph()
        state = AgentState()
        portfolio = {Asset("XRP", None): 1000.0}
        initial_base = value_in_base(
            Asset("XRP", None), 1000.0, cfg.BASE_ASSET, graph, cfg
        )

        trades = 0
        holds = 0
        for step in range(1000):
            choice, used = greedy_agent_step(
                graph,
                portfolio,
                fee_fraction=cfg.TRADING_FEE,
                max_hops=cfg.MAX_HOPS,
                max_paths=cfg.MAX_PATHS,
                step=step,
                state=state,
                cfg=cfg,
            )
            if choice is None or used == "":
                holds += 1
                continue
            trades += 1
            amt = portfolio.get(used, 0.0)
            if amt <= 0:
                break
            portfolio[used] = 0.0
            dst = choice.path[-1]
            portfolio[dst] = portfolio.get(dst, 0.0) + choice.output_amount

        final_base = 0.0
        for asset, amount in portfolio.items():
            if amount <= 0:
                continue
            final_base += value_in_base(asset, amount, cfg.BASE_ASSET, graph, cfg)

        total_steps = trades + holds
        hold_ratio = (holds / total_steps) if total_steps else 0.0
        self.assertGreaterEqual(final_base, 0.5 * initial_base)
        self.assertGreaterEqual(hold_ratio, 0.7)

    def test_reversal_blocked_during_cooldown(self):
        a = Asset("A", None)
        b = Asset("B", None)
        graph = {
            a: [
                MarketEdge(src=a, dst=b, levels=[Level(rate=1.1, capacity=1_000_000.0)])
            ],
            b: [
                MarketEdge(src=b, dst=a, levels=[Level(rate=1.1, capacity=1_000_000.0)])
            ],
        }
        test_cfg = SimpleNamespace(
            BASE_ASSET=Asset("A", None),
            DEFAULT_ISSUER=cfg.DEFAULT_ISSUER,
            BASE_VALUE_MAX_HOPS=3,
            BASE_VALUE_MAX_PATHS=3,
            TRADING_FEE=0.0,
            MIN_BASE_GAIN_MULT=1.001,
            COOLDOWN_STEPS=2,
            REVERSE_BLOCK=True,
        )

        state = AgentState()
        portfolio = {a: 100.0}

        choice1, used1 = greedy_agent_step(
            graph,
            portfolio,
            fee_fraction=0.0,
            max_hops=2,
            max_paths=3,
            step=0,
            state=state,
            cfg=test_cfg,
        )
        self.assertIsNotNone(choice1)
        self.assertEqual(used1, a)
        self.assertEqual(choice1.path[-1], b)

        portfolio[a] = 0.0
        portfolio[b] = choice1.output_amount

        choice2, used2 = greedy_agent_step(
            graph,
            portfolio,
            fee_fraction=0.0,
            max_hops=2,
            max_paths=3,
            step=1,
            state=state,
            cfg=test_cfg,
        )
        self.assertIsNone(choice2)
        self.assertEqual(used2, "")


if __name__ == "__main__":
    unittest.main()
