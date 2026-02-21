"""
Arbitrage scanner: run Bellman-Ford, extract cycle, simulate realistic fill, report profit after fees.
"""
import logging
from dataclasses import dataclass

from .graph import MarketEdge
from .routing import bellman_ford_negative_cycle
from .simulate import simulate_path
from .config import TRADING_FEE

logger = logging.getLogger(__name__)


@dataclass
class ArbitrageReport:
    """One arbitrage opportunity: cycle, profit estimate, confidence heuristic."""
    cycle: list[str]
    profit_pct: float
    profit_absolute: float
    input_amount: float
    output_after_fees: float
    confidence: float  # 0-1 heuristic


def scan_arbitrage(
    graph: dict[str, list[MarketEdge]],
    trial_amount: float = 1000.0,
    fee_fraction: float = TRADING_FEE,
) -> ArbitrageReport | None:
    """
    Run Bellman-Ford; if negative cycle exists, simulate fill with trial_amount,
    report profit after fees. Returns None if no cycle.
    """
    cycle = bellman_ford_negative_cycle(graph)
    if not cycle or len(cycle) < 2:
        return None
    # Cycle is e.g. [A, B, C, A]. Simulate A -> B -> C -> A
    sim = simulate_path(cycle, graph, trial_amount, fee_fraction)
    output = sim.output_amount
    profit_abs = output - trial_amount
    profit_pct = (profit_abs / trial_amount) * 100.0 if trial_amount > 0 else 0.0
    # Confidence: 1 if fully filled, else scaled by fill ratio
    confidence = 1.0 if sim.fully_filled else max(0.0, sim.output_amount / trial_amount)
    return ArbitrageReport(
        cycle=cycle,
        profit_pct=profit_pct,
        profit_absolute=profit_abs,
        input_amount=trial_amount,
        output_after_fees=output,
        confidence=confidence,
    )
