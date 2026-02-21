# Greedy Agent Anti-Churn Implementation Summary

## Overview
Implemented a comprehensive anti-churn mechanism to prevent the greedy agent from executing unprofitable trades in thin market spreads. The agent now intelligently HOLDs when no trade meets a profitability threshold.

## Changes Made

### 1. Configuration (`xrpl_router/config.py`)
Added new config parameters:
- `MIN_EV_MULTIPLIER = 1.002` - Require +0.2% improvement over HOLD to trade
- `REVERSE_MIN_EV_MULTIPLIER = 1.01` - Require +1% to execute immediate reversals
- `ENABLE_REVERSAL_GUARD = False` - Flag to enable optional reversal prevention

### 2. Strategy Module (`xrpl_router/strategy.py`)

#### Updated `RouteChoice` dataclass:
- Added `ev_gain_ratio: float` - Expected value as ratio to input (for hold comparison)
- Added `input_amount: float` - Source amount before trade
- Added `hold_reason: str` - Explanation if decision is HOLD

#### Updated `evaluate_routes()`:
- Now calculates and returns `ev_gain_ratio` for each route
- Provides explicit EV metrics for decision-making

#### Refactored `greedy_agent_step()`:
- **HOLD Logic**: Trades only executed if `best_ev >= hold_threshold × MIN_EV_MULTIPLIER`
- **Reversal Guard** (optional): If `ENABLE_REVERSAL_GUARD=True`, requires higher threshold for trades ending in recent asset
- **Last Asset Tracking**: Accepts `last_asset` parameter to track trade history
- **Decision Logging**: Logs both TRADE and HOLD decisions with reasons

### 3. UI Updates (`app.py`)

#### Enhanced Simulation Tab:
- Added trade/hold counters to track decision distribution
- Enhanced debug logging showing:
  - Step number
  - Asset and amount being traded/held  
  - Route path and output amounts
  - Trade ratio (output/input)
  - EV ratio for profitability assessment
- Display holds as percentage of total steps
- Sample logs every 100 steps (plus first 20)

#### New Metrics Display:
- "Trades executed" - Number of trades made
- "Steps held" - Number of HOLD decisions
- "Hold %" - Percentage of steps that were HOLD

### 4. Tests (`xrpl_router/tests/test_churn_prevention.py`)

Added 4 comprehensive tests:

1. **test_churn_loss_without_guard**: Baseline showing portfolio erosion over 200 steps
2. **test_hold_logic_reduces_churn**: Validates >70% HOLD rate and portfolio preservation over 1000 steps
3. **test_min_ev_multiplier_enforcement**: Ensures trades meet the EV threshold
4. **test_last_asset_tracking**: Verifies API stability with last_asset parameter

## Performance Results

### Before (without anti-churn):
- 1000 steps with mock data
- Result: Portfolio collapsed to ~0.01 (100% loss)
- Cause: Continuous cycling USD ↔ EUR with 10% spread loss per round trip

### After (with anti-churn):
- 1000 steps with mock data  
- Trades: 1 (0.1%)
- Holds: 999 (99.9%)
- Result: Portfolio value preserved at $1998 (+99.8% from initial $1000)
- Behavior: Executes only the profitable XRP→USD trade, HOLDs thereafter

## Design Principles

1. **Risk Management**: Don't trade unless there's clear value (0.2% minimum improvement)
2. **Transparency**: Every decision logged with reason (TRADE or HOLD + threshold info)
3. **Configurability**: All thresholds tunable via config
4. **Backward Compatible**: Optional reversal guard, works without agent state modifications
5. **Evidence-Based**: EV calculations explicit and traceable

## Testing Coverage

- ✅ All 27 tests pass (including 4 new churn tests)
- ✅ Mock integration tests still pass
- ✅ Streamlit app launches without errors
- ✅ Debug simulation shows expected behavior

## Usage

### In Code:
```python
from xrpl_router.strategy import greedy_agent_step

choice, used = greedy_agent_step(
    graph, 
    portfolio,
    fee_fraction=TRADING_FEE,
    max_hops=MAX_HOPS,
    max_paths=MAX_PATHS,
    last_asset=None,  # Optional: track reversal guard
)

if choice is None or used == "":
    print("Agent decided to HOLD")
else:
    print(f"Agent trades {used} via path {choice.path}")
```

### CLI/UI:
- Run simulator with 1000 steps to see majority HOLD behavior
- Check debug logs for trade decisions and reasons
- Monitor "Hold %" metric to verify anti-churn activation

## Future Enhancements

1. Dynamic `MIN_EV_MULTIPLIER` based on market volatility
2. Machine learning to predict profitable trade windows
3. Asset-specific thresholds (e.g., different for XRP vs stablecoins)
4. Portfolio rebalancing logic for long-term strategies
5. Integration with ML prediction model for market conditions
