"""
Slippage simulation: execute a path with capacity-constrained level-by-level fill.
Applies configurable per-hop fees. Returns final output, fully_filled, effective rate.
"""

from dataclasses import dataclass
from typing import Callable

from .graph import MarketEdge, Asset
from .config import TRADING_FEE, FAILURE_PENALTY


@dataclass
class SimResult:
    """Result of simulating execution along a path."""

    output_amount: float
    fully_filled: bool
    effective_rate: float
    hops_executed: int
    fill_ratios: list[float]  # per-hop fill ratio (output / input)
    avg_rates: list[float]  # per-hop effective rate


def simulate_path(
    path: list[Asset],
    graph: dict[Asset, list[MarketEdge]],
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
            fill_ratios=[],
            avg_rates=[],
        )
    amount = input_amount
    hops_done = 0
    fill_ratios = []
    avg_rates = []
    fully_filled = True
    for i in range(len(path) - 1):
        src, dst = path[i], path[i + 1]
        edge = _find_edge(graph, src, dst)
        if edge is None:
            return SimResult(
                output_amount=0.0,
                fully_filled=False,
                effective_rate=0.0,
                hops_executed=hops_done,
                fill_ratios=fill_ratios,
                avg_rates=avg_rates,
            )
        input_to_hop = amount
        output_from_hop, hop_fully_filled, hop_avg_rate = _fill_levels(amount, edge)
        fill_ratios.append(output_from_hop / input_to_hop if input_to_hop > 0 else 0)
        avg_rates.append(hop_avg_rate)
        if not hop_fully_filled:
            fully_filled = False
        amount = output_from_hop
        if amount <= 0:
            return SimResult(
                output_amount=0.0,
                fully_filled=False,
                effective_rate=0.0,
                hops_executed=hops_done + 1,
                fill_ratios=fill_ratios,
                avg_rates=avg_rates,
            )
        amount *= 1.0 - fee_fraction
        hops_done += 1
    output = amount
    effective = output / input_amount if input_amount > 0 else 0.0
    return SimResult(
        output_amount=output,
        fully_filled=fully_filled,
        effective_rate=effective,
        hops_executed=hops_done,
        fill_ratios=fill_ratios,
        avg_rates=avg_rates,
    )


def _find_edge(
    graph: dict[Asset, list[MarketEdge]], src: Asset, dst: Asset
) -> MarketEdge | None:
    """Return first edge from src to dst (best rate is first in our construction)."""
    for e in graph.get(src, []):
        if e.dst == dst:
            return e
    return None


def _fill_levels(amount_src: float, edge: MarketEdge) -> tuple[float, bool, float]:
    """
    Consume amount_src of edge.src along edge levels; return (amount_dst, fully_filled, avg_rate).
    Fills best level first, then next, until amount_src exhausted or liquidity exhausted.
    fully_filled if remaining_src <= 1e-6
    avg_rate = total_dst / amount_src
    """
    remaining_src = amount_src
    total_dst = 0.0
    for level in edge.levels:
        if remaining_src <= 0:
            break
        fill_src = min(remaining_src, level.capacity)
        total_dst += fill_src * level.rate
        remaining_src -= fill_src
    fully_filled = remaining_src <= 1e-6
    avg_rate = total_dst / amount_src if amount_src > 0 else 0.0
    return total_dst, fully_filled, avg_rate


def compute_success_probability(
    path: list[Asset], graph: dict[Asset, list[MarketEdge]], input_amount: float
) -> float:
    """
    Compute success probability for executing the path with given input_amount.
    For each hop, p_h based on available liquidity vs needed.
    """
    if len(path) < 2:
        return 1.0
    p_success = 1.0
    amount = input_amount
    for i in range(len(path) - 1):
        src, dst = path[i], path[i + 1]
        edge = _find_edge(graph, src, dst)
        if edge is None:
            return 0.0
        needed = amount
        available = sum(level.capacity for level in edge.levels)
        safety_margin = 0.15
        if available >= needed * (1 + safety_margin):
            p_h = 0.98
        elif available >= needed:
            p_h = 0.80
        else:
            p_h = 0.0
        p_success *= p_h
        # Simulate the amount after this hop (without fee for probability)
        amount = _fill_levels(amount, edge)[0]  # just the output
    return p_success
