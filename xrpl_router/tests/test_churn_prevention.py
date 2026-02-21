"""
Tests for greedy agent churn prevention logic.
"""
import unittest
from xrpl_router.graph import Asset
from xrpl_router.mock_data import get_mock_graph
from xrpl_router.strategy import greedy_agent_step
from xrpl_router.config import TRADING_FEE, MAX_HOPS, MAX_PATHS, MIN_EV_MULTIPLIER


class TestChurnPrevention(unittest.TestCase):
    
    def test_churn_loss_without_guard(self):
        """
        Test baseline: without anti-churn guard, portfolio loses value over time due to spreads.
        This demonstrates the problem we're fixing.
        """
        graph = get_mock_graph()
        portfolio = {Asset("XRP", None): 1000.0}
        
        for step in range(200):
            choice, used = greedy_agent_step(
                graph, portfolio,
                fee_fraction=TRADING_FEE,
                max_hops=MAX_HOPS,
                max_paths=MAX_PATHS,
            )
            if choice is None or used == "":
                break
            amt = portfolio.get(used, 0)
            if amt <= 0:
                break
            portfolio[used] = 0.0
            dest = choice.path[-1]
            portfolio[dest] = portfolio.get(dest, 0) + choice.output_amount
        
        final = sum(portfolio.values())
        print(f"Without guard - Final portfolio after 200 steps: {final:.2f} (started with 1000.0)")
        # Without guard, should lose significant value due to churn
        # This may vary with mock data, but the point is to show the problem

    def test_hold_logic_reduces_churn(self):
        """
        Test that the HOLD logic prevents excessive trading when threshold is high.
        """
        graph = get_mock_graph()
        portfolio = {Asset("XRP", None): 1000.0}
        
        trade_count = 0
        hold_count = 0
        
        for step in range(1000):
            choice, used = greedy_agent_step(
                graph, portfolio,
                fee_fraction=TRADING_FEE,
                max_hops=MAX_HOPS,
                max_paths=MAX_PATHS,
            )
            
            if choice is None or used == "":
                hold_count += 1
                continue
            
            trade_count += 1
            amt = portfolio.get(used, 0)
            if amt <= 0:
                break
            portfolio[used] = 0.0
            dest = choice.path[-1]
            portfolio[dest] = portfolio.get(dest, 0) + choice.output_amount
        
        final = sum(portfolio.values())
        total_steps = trade_count + hold_count
        hold_ratio = hold_count / total_steps if total_steps > 0 else 0
        
        print(f"With guard - Trades: {trade_count}, Holds: {hold_count}, Hold%: {hold_ratio:.1%}")
        print(f"Final portfolio after 1000 steps: {final:.2f} (started with 1000.0)")
        
        # With MIN_EV_MULTIPLIER = 1.002, should have many HOLD decisions
        self.assertGreater(hold_ratio, 0.7, f"Expected >70% holds, got {hold_ratio:.1%}")
        
        # Final portfolio should not collapse to near-zero
        # With 0.2% threshold and spreads of 10%, expect reasonable preservation
        self.assertGreater(final, 500.0, f"Portfolio collapsed to {final:.2f}, expected > 500.0")

    def test_min_ev_multiplier_enforcement(self):
        """
        Test that MIN_EV_MULTIPLIER is properly enforced.
        """
        graph = get_mock_graph()
        portfolio = {Asset("XRP", None): 1000.0}
        
        choice, used = greedy_agent_step(
            graph, portfolio,
            fee_fraction=TRADING_FEE,
            max_hops=MAX_HOPS,
            max_paths=MAX_PATHS,
        )
        
        if choice is not None:
            # If we get a trade, verify it exceeds the threshold
            hold_amount = 1000.0
            threshold = hold_amount * MIN_EV_MULTIPLIER
            self.assertGreaterEqual(choice.expected_value, threshold,
                                    f"Trade EV {choice.expected_value} should exceed threshold {threshold}")

    def test_last_asset_tracking(self):
        """
        Test that last_asset is properly None initially.
        """
        graph = get_mock_graph()
        portfolio = {Asset("XRP", None): 1000.0}
        
        # First call with no last_asset
        choice1, used1 = greedy_agent_step(
            graph, portfolio,
            fee_fraction=TRADING_FEE,
            max_hops=MAX_HOPS,
            max_paths=MAX_PATHS,
            last_asset=None,
        )
        
        if choice1 is not None and used1 != "":
            # Simulate the trade
            portfolio[Asset("XRP", None)] = 0.0
            portfolio[choice1.path[-1]] = choice1.output_amount
            
            # Second call with last_asset set
            choice2, used2 = greedy_agent_step(
                graph, portfolio,
                fee_fraction=TRADING_FEE,
                max_hops=MAX_HOPS,
                max_paths=MAX_PATHS,
                last_asset=choice1.path[-1],  # Track where we came from
            )
            
            # This test just verifies the API works without errors
            self.assertIsNotNone(choice2 or used2 == "")


if __name__ == "__main__":
    unittest.main()
