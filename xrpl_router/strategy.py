"""
Opportunity evaluation: generate candidate routes (k-shortest / max-hop limited),
simulate slippage, compute expected value, choose best (greedy).
"""
import logging
from collections import deque
from dataclasses import dataclass
from typing import Callable

from .graph import MarketEdge
from .simulate import simulate_path
from .config import MAX_HOPS, MAX_PATHS, TRADING_FEE, RISK_PENALTY, DEFAULT_SUCCESS_PROBABILITY

logger = logging.getLogger(__name__)


@dataclass
class RouteChoice:
    """Best route choice: path, expected value, simulated output, success probability."""
    path: list[str]
    expected_value: float
    output_amount: float
    success_probability: float
    effective_rate: float


def generate_candidate_paths(
    graph: dict[str, list[MarketEdge]],
    source: str,
    max_hops: int = MAX_HOPS,
    max_paths: int = MAX_PATHS,
) -> list[list[str]]:
    """
    Generate candidate paths from source with length in [2, max_hops+1].
    Uses BFS; returns up to max_paths paths (prefer shorter, then by destination).
    """
    if source not in graph:
        return []
    paths: list[list[str]] = []
    queue: deque[tuple[str, list[str]]] = deque([(source, [source])])
    seen: set[tuple[str, ...]] = set()
    while queue and len(paths) < max_paths * 3:
        node, path = queue.popleft()
        if len(path) >= 2:
            paths.append(path[:])
        if len(path) > max_hops:
            continue
        for edge in graph.get(node, []):
            if edge.dst in path:
                continue
            key = (tuple(path), edge.dst)
            if key in seen:
                continue
            seen.add(key)
            queue.append((edge.dst, path + [edge.dst]))
    paths.sort(key=lambda p: (len(p), p[-1]))
    return paths[:max_paths]


def evaluate_routes(
    graph: dict[str, list[MarketEdge]],
    source: str,
    amount: float,
    fee_fraction: float = TRADING_FEE,
    risk_penalty: float = RISK_PENALTY,
    success_probability: float | None = None,
    max_hops: int = MAX_HOPS,
    max_paths: int = MAX_PATHS,
) -> RouteChoice | None:
    """
    Generate candidate routes from source, simulate each, compute
    EV = P(success) * output - cost (cost = amount); apply risk penalty to P.
    Return best route choice or None.
    """
    paths = generate_candidate_paths(graph, source, max_hops=max_hops, max_paths=max_paths)
    if not paths:
        return None
    p_success = success_probability if success_probability is not None else DEFAULT_SUCCESS_PROBABILITY
    p_success = max(0.0, min(1.0, p_success - risk_penalty))
    best: RouteChoice | None = None
    for path in paths:
        if len(path) < 2:
            continue
        sim = simulate_path(path, graph, amount, fee_fraction)
        cost = amount
        ev = p_success * sim.output_amount - cost
        if best is None or ev > best.expected_value:
            best = RouteChoice(
                path=path,
                expected_value=ev,
                output_amount=sim.output_amount,
                success_probability=p_success,
                effective_rate=sim.effective_rate,
            )
    return best


def greedy_agent_step(
    graph: dict[str, list[MarketEdge]],
    portfolio: dict[str, float],
    fee_fraction: float = TRADING_FEE,
    max_hops: int = MAX_HOPS,
    max_paths: int = MAX_PATHS,
) -> tuple[RouteChoice | None, str]:
    """
    From current portfolio, pick asset with positive balance and choose best route.
    Returns (best_choice, asset_used) or (None, "") if no positive balance or no route.
    """
    best: RouteChoice | None = None
    asset_used = ""
    for asset, balance in portfolio.items():
        if balance <= 0:
            continue
        choice = evaluate_routes(
            graph, asset, balance,
            fee_fraction=fee_fraction,
            max_hops=max_hops,
            max_paths=max_paths,
        )
        if choice and choice.expected_value > 0 and (best is None or choice.expected_value > best.expected_value):
            best = choice
            asset_used = asset
    return best, asset_used
