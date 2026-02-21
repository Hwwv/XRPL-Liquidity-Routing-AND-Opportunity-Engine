"""
Tests for base-asset scoring and cooldown/reversal protection.
"""

import unittest
from types import SimpleNamespace

from xrpl_router import config as cfg
from xrpl_router.graph import Asset, MarketEdge
from xrpl_router.mock_data import get_mock_graph
from xrpl_router.orderbooks import Level
from xrpl_router.strategy import (
    STRATEGY_EXTENDED_GREEDY,
    STRATEGY_GREEDY,
    AgentState,
    greedy_agent_step,
)
from xrpl_router.valuation import value_in_base


class TestChurnPrevention(unittest.TestCase):
    def _run_steps(
        self,
        graph,
        strategy_mode: str,
        steps: int = 1000,
        start_asset: Asset = Asset("XRP", None),
        start_amount: float = 1000.0,
        test_cfg=cfg,
    ) -> tuple[dict[Asset, float], int, int]:
        state = AgentState()
        portfolio = {start_asset: start_amount}
        trades = 0
        holds = 0
        for step in range(steps):
            choice, used = greedy_agent_step(
                graph,
                portfolio,
                fee_fraction=test_cfg.TRADING_FEE,
                max_hops=test_cfg.MAX_HOPS,
                max_paths=test_cfg.MAX_PATHS,
                step=step,
                state=state,
                cfg=test_cfg,
                strategy_mode=strategy_mode,
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
        return portfolio, trades, holds

    def _portfolio_in_base(self, portfolio, graph, base_asset, test_cfg) -> float:
        total = 0.0
        for asset, amount in portfolio.items():
            if amount <= 0:
                continue
            total += value_in_base(asset, amount, base_asset, graph, test_cfg)
        return total

    def test_long_run_mock_does_not_collapse(self):
        graph = get_mock_graph()
        portfolio, trades, holds = self._run_steps(
            graph,
            strategy_mode=STRATEGY_GREEDY,
            steps=1000,
            start_asset=Asset("XRP", None),
            start_amount=1000.0,
            test_cfg=cfg,
        )
        initial_base = value_in_base(
            Asset("XRP", None), 1000.0, cfg.BASE_ASSET, graph, cfg
        )
        final_base = self._portfolio_in_base(portfolio, graph, cfg.BASE_ASSET, cfg)

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
            BASE_VALUE_MAX_HOPS=1,
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

    def test_lookahead_prefers_better_two_step_first_action(self):
        a = Asset("A", None)
        b = Asset("B", None)
        c = Asset("C", None)
        d = Asset("D", None)
        graph = {
            a: [
                MarketEdge(
                    src=a, dst=b, levels=[Level(rate=1.03, capacity=1_000_000.0)]
                ),
                MarketEdge(
                    src=a, dst=c, levels=[Level(rate=1.01, capacity=1_000_000.0)]
                ),
            ],
            b: [
                MarketEdge(src=b, dst=a, levels=[Level(rate=1.0, capacity=1_000_000.0)])
            ],
            c: [
                MarketEdge(
                    src=c, dst=a, levels=[Level(rate=1.0, capacity=1_000_000.0)]
                ),
                MarketEdge(
                    src=c, dst=d, levels=[Level(rate=1.1, capacity=1_000_000.0)]
                ),
            ],
            d: [
                MarketEdge(src=d, dst=a, levels=[Level(rate=1.0, capacity=1_000_000.0)])
            ],
        }
        test_cfg = SimpleNamespace(
            BASE_ASSET=Asset("A", None),
            DEFAULT_ISSUER=cfg.DEFAULT_ISSUER,
            TRADING_FEE=0.0,
            MIN_BASE_GAIN_MULT=1.0,
            COOLDOWN_STEPS=0,
            REVERSE_BLOCK=False,
            BASE_VALUE_MAX_HOPS=1,
            BASE_VALUE_MAX_PATHS=5,
            LOOKAHEAD_TOPK=5,
            LOOKAHEAD_MAX_HOPS=1,
            LOOKAHEAD_MAX_PATHS=5,
            MAX_HOPS=1,
            MAX_PATHS=5,
        )
        portfolio_greedy = {a: 100.0}
        portfolio_extended = {a: 100.0}

        greedy_choice, _ = greedy_agent_step(
            graph,
            portfolio_greedy,
            fee_fraction=0.0,
            max_hops=1,
            max_paths=5,
            step=0,
            state=AgentState(),
            cfg=test_cfg,
            strategy_mode=STRATEGY_GREEDY,
        )
        extended_choice, _ = greedy_agent_step(
            graph,
            portfolio_extended,
            fee_fraction=0.0,
            max_hops=1,
            max_paths=5,
            step=0,
            state=AgentState(),
            cfg=test_cfg,
            strategy_mode=STRATEGY_EXTENDED_GREEDY,
        )
        self.assertIsNotNone(greedy_choice)
        self.assertIsNotNone(extended_choice)
        self.assertEqual(greedy_choice.path[-1], b)
        self.assertEqual(extended_choice.path[-1], c)

    def test_extended_greedy_long_run_outperforms_or_matches_greedy(self):
        graph = get_mock_graph()
        portfolio_greedy, _, _ = self._run_steps(
            graph,
            strategy_mode=STRATEGY_GREEDY,
            steps=1000,
            start_asset=Asset("XRP", None),
            start_amount=1000.0,
            test_cfg=cfg,
        )
        portfolio_extended, _, _ = self._run_steps(
            graph,
            strategy_mode=STRATEGY_EXTENDED_GREEDY,
            steps=1000,
            start_asset=Asset("XRP", None),
            start_amount=1000.0,
            test_cfg=cfg,
        )
        greedy_base = self._portfolio_in_base(
            portfolio_greedy, graph, cfg.BASE_ASSET, cfg
        )
        extended_base = self._portfolio_in_base(
            portfolio_extended, graph, cfg.BASE_ASSET, cfg
        )
        initial_base = value_in_base(
            Asset("XRP", None), 1000.0, cfg.BASE_ASSET, graph, cfg
        )
        self.assertGreaterEqual(extended_base, greedy_base)
        self.assertGreaterEqual(extended_base, 0.5 * initial_base)


if __name__ == "__main__":
    unittest.main()
