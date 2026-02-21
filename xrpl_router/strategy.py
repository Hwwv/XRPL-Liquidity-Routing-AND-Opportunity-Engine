"""
Opportunity evaluation: generate candidate routes (k-shortest / max-hop limited),
simulate slippage, compute expected value, choose best (greedy).
"""
import logging
from collections import deque
from dataclasses import dataclass
from typing import Callable

from .graph import MarketEdge, Asset
from .simulate import simulate_path, compute_success_probability
from .config import MAX_HOPS, MAX_PATHS, TRADING_FEE, RISK_PENALTY, DEFAULT_SUCCESS_PROBABILITY, FAILURE_PENALTY, LAMBDA_HOPS, LAMBDA_SPREAD, LAMBDA_DEPTH
from .graph import Asset


def _resolve_asset(s: str) -> Asset:
    from .config import DEFAULT_ISSUER
    s = (s or "").strip()
    if not s:
        return Asset("XRP", None)
    if s.upper() == "XRP":
        return Asset("XRP", None)
    if ":" in s:
        cur, iss = s.split(":", 1)
        return Asset(cur.upper(), iss.strip() or None)
    return Asset(s.upper(), DEFAULT_ISSUER)

logger = logging.getLogger(__name__)


@dataclass
class RouteChoice:
    """Best route choice: path, expected value, simulated output, success probability."""
    path: list[Asset]
    expected_value: float
    output_amount: float
    success_probability: float
    effective_rate: float
    score: float


def generate_candidate_paths(
    graph: dict[Asset, list[MarketEdge]],
    source: Asset,
    max_hops: int = MAX_HOPS,
    max_paths: int = MAX_PATHS,
) -> list[list[Asset]]:
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
    paths.sort(key=lambda p: (len(p), str(p[-1])))
    return paths[:max_paths]


def evaluate_routes(
    graph: dict[Asset, list[MarketEdge]],
    source: Asset,
    amount: float,
    fee_fraction: float = TRADING_FEE,
    risk_penalty: float = RISK_PENALTY,
    success_probability: float | None = None,
    max_hops: int = MAX_HOPS,
    max_paths: int = MAX_PATHS,
) -> RouteChoice | None:
    """
    Generate candidate routes from source, simulate each, compute
    EV = P(success) * output - (1 - P(success)) * failure_penalty
    Return best route choice or None.
    """
    paths = generate_candidate_paths(graph, source, max_hops=max_hops, max_paths=max_paths)
    if not paths:
        return None
    best: RouteChoice | None = None
    for path in paths:
        if len(path) < 2:
            continue
        p_success = compute_success_probability(path, graph, amount)
        sim = simulate_path(path, graph, amount, fee_fraction)
        ev = p_success * sim.output_amount - (1 - p_success) * FAILURE_PENALTY
        hop_count = len(path) - 1
        spread_penalty = 0.0  # placeholder
        depth_penalty = 0.0  # placeholder
        score = ev - LAMBDA_HOPS * hop_count - LAMBDA_SPREAD * spread_penalty - LAMBDA_DEPTH * depth_penalty
        if best is None or score > best.score:
            best = RouteChoice(
                path=path,
                expected_value=ev,
                output_amount=sim.output_amount,
                success_probability=p_success,
                effective_rate=sim.effective_rate,
                score=score,
            )
    return best


def greedy_agent_step(
    graph: dict[Asset, list[MarketEdge]],
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
    for asset_str, balance in portfolio.items():
        if balance <= 0:
            continue
        # Convert str to Asset
        if isinstance(asset_str, str):
            asset = _resolve_asset(asset_str)
        else:
            asset = asset_str
        choice = evaluate_routes(
            graph, asset, balance,
            fee_fraction=fee_fraction,
            max_hops=max_hops,
            max_paths=max_paths,
        )
        if choice and choice.score > 0 and (best is None or choice.score > best.score):
            best = choice
            asset_used = asset_str
    return best, asset_used
