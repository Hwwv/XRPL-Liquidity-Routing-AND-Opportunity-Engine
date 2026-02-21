"""
Slippage simulation: execute a path with capacity-constrained level-by-level fill.
Applies configurable per-hop fees. Returns final output, fully_filled, effective rate.
"""
from dataclasses import dataclass
from typing import Callable

from .graph import MarketEdge
from .config import TRADING_FEE


@dataclass
class SimResult:
    """Result of simulating execution along a path."""
    output_amount: float
    fully_filled: bool
    effective_rate: float
    hops_executed: int


def simulate_path(
    path: list[str],
    graph: dict[str, list[MarketEdge]],
    input_amount: float,
    fee_fraction: float = TRADING_FEE,
) -> SimResult:
    """
    Simulate execution along path [A, B, C, ...]:
    - At each hop, fill best level first, then next levels until amount exhausted or done.
    - After each hop, apply fee: remaining *= (1 - fee_fraction).
    - Return final output, whether fully filled, and effective rate (output/input).
    """
    if len(path) < 2:
        return SimResult(
            output_amount=input_amount,
            fully_filled=True,
            effective_rate=1.0,
            hops_executed=0,
        )
    amount = input_amount
    hops_done = 0
    for i in range(len(path) - 1):
        src, dst = path[i], path[i + 1]
        edge = _find_edge(graph, src, dst)
        if edge is None:
            return SimResult(
                output_amount=0.0,
                fully_filled=False,
                effective_rate=0.0,
                hops_executed=hops_done,
            )
        amount = _fill_levels(amount, edge)
        if amount <= 0:
            return SimResult(
                output_amount=0.0,
                fully_filled=False,
                effective_rate=0.0,
                hops_executed=hops_done,
            )
        amount *= 1.0 - fee_fraction
        hops_done += 1
    output = amount
    effective = output / input_amount if input_amount > 0 else 0.0
    return SimResult(
        output_amount=output,
        fully_filled=True,
        effective_rate=effective,
        hops_executed=hops_done,
    )


def _find_edge(graph: dict[str, list[MarketEdge]], src: str, dst: str) -> MarketEdge | None:
    """Return first edge from src to dst (best rate is first in our construction)."""
    for e in graph.get(src, []):
        if e.dst == dst:
            return e
    return None


def _fill_levels(amount_src: float, edge: MarketEdge) -> float:
    """
    Consume amount_src of edge.src along edge levels; return amount of edge.dst received.
    Fills best level first, then next, until amount_src exhausted or liquidity exhausted.
    """
    remaining_src = amount_src
    total_dst = 0.0
    for level in edge.levels:
        if remaining_src <= 0:
            break
        fill_src = min(remaining_src, level.capacity)
        total_dst += fill_src * level.rate
        remaining_src -= fill_src
    return total_dst
