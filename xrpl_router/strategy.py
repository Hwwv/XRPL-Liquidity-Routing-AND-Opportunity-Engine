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
from .config import MAX_HOPS, MAX_PATHS, TRADING_FEE, RISK_PENALTY, DEFAULT_SUCCESS_PROBABILITY, FAILURE_PENALTY, LAMBDA_HOPS, LAMBDA_SPREAD, LAMBDA_DEPTH, MIN_EV_MULTIPLIER, REVERSE_MIN_EV_MULTIPLIER, ENABLE_REVERSAL_GUARD
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
    ev_gain_ratio: float  # expected_value / input_amount (for hold comparison)
    input_amount: float  # source amount before trade
    hold_reason: str = ""  # reason if this is a HOLD decision


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
        ev_gain_ratio = ev / amount if amount > 0 else 0.0
        if best is None or score > best.score:
            best = RouteChoice(
                path=path,
                expected_value=ev,
                output_amount=sim.output_amount,
                success_probability=p_success,
                effective_rate=sim.effective_rate,
                score=score,
                ev_gain_ratio=ev_gain_ratio,
                input_amount=amount,
            )
    return best


def greedy_agent_step(
    graph: dict[Asset, list[MarketEdge]],
    portfolio: dict[str, float],
    fee_fraction: float = TRADING_FEE,
    max_hops: int = MAX_HOPS,
    max_paths: int = MAX_PATHS,
    last_asset: Asset | None = None,  # track previous destination for reversal guard
) -> tuple[RouteChoice | None, str]:
    """
    From current portfolio, pick asset with positive balance and choose best route.
    Implements HOLD logic: only trade if EV significantly exceeds hold_ev (baseline = current_amount).
    
    Returns (best_choice, asset_used):
    - best_choice is a RouteChoice if trading, or a HOLD marker with path=[], or None if no balance
    - asset_used is the asset key we're trading from (or "" if HOLD)
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
        if choice and choice.score > 0:
            # Check reversal guard: if destination is recent source, require higher threshold
            if ENABLE_REVERSAL_GUARD and last_asset is not None and choice.path[-1] == last_asset:
                reversal_threshold = balance * REVERSE_MIN_EV_MULTIPLIER
                if choice.expected_value < reversal_threshold:
                    choice.hold_reason = f"reversal guard: EV {choice.expected_value:.2f} < {reversal_threshold:.2f}"
                    logger.debug(f"Reversal guard triggered: {asset} → {choice.path[-1]}, {choice.hold_reason}")
                    continue
            
            # Main threshold: require MIN_EV_MULTIPLIER improvement over HOLD
            hold_threshold = balance * MIN_EV_MULTIPLIER
            if choice.expected_value < hold_threshold:
                choice.hold_reason = f"below threshold: EV {choice.expected_value:.2f} < {hold_threshold:.2f}"
                logger.debug(f"Below threshold: {asset}, {choice.hold_reason}")
                continue
            
            if best is None or choice.score > best.score:
                best = choice
                asset_used = asset_str
    
    if best is None:
        logger.debug("No profitable trade found, signaling HOLD")
        return None, ""
    
    return best, asset_used
