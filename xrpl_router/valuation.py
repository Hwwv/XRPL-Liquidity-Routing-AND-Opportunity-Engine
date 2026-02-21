"""
Base-asset valuation helpers.
"""

from collections import deque

from .config import (
    BASE_VALUE_MAX_HOPS,
    BASE_VALUE_MAX_PATHS,
    DEFAULT_ISSUER,
    TRADING_FEE,
)
from .graph import Asset, MarketEdge
from .simulate import simulate_path


def _resolve_asset(asset: Asset | str, default_issuer: str = DEFAULT_ISSUER) -> Asset:
    if isinstance(asset, Asset):
        return asset
    s = (asset or "").strip()
    if not s or s.upper() == "XRP":
        return Asset("XRP", None)
    if ":" in s:
        cur, iss = s.split(":", 1)
        return Asset(cur.upper(), iss.strip() or None)
    return Asset(s.upper(), default_issuer)


def _candidate_paths_to_target(
    graph: dict[Asset, list[MarketEdge]],
    source: Asset,
    target: Asset,
    max_hops: int,
    max_paths: int,
) -> list[list[Asset]]:
    if source not in graph:
        return []
    if source == target:
        return [[source]]

    candidates: list[tuple[list[Asset], float]] = []
    queue: deque[tuple[Asset, list[Asset], float]] = deque([(source, [source], 1.0)])
    while queue and len(candidates) < max_paths * 6:
        node, path, approx = queue.popleft()
        hop_count = len(path) - 1
        if hop_count >= max_hops:
            continue
        for edge in graph.get(node, []):
            if edge.dst in path:
                continue
            edge_rate = edge.best_rate() or 0.0
            next_path = path + [edge.dst]
            next_approx = approx * edge_rate
            if edge.dst == target:
                candidates.append((next_path, next_approx))
                continue
            queue.append((edge.dst, next_path, next_approx))

    candidates.sort(key=lambda x: (len(x[0]), -x[1]))
    return [path for path, _ in candidates[:max_paths]]


def value_in_base(asset, amount, base_asset, graph, cfg) -> float:
    """
    Return best estimated amount of base_asset obtainable from (asset, amount).
    Uses existing routing + simulate_path (fees+slippage).
    Fast: cap hops and number of candidate paths.
    - if asset == base_asset: return amount
    - if no route found or fill fails: return 0.0
    """
    try:
        amount = float(amount)
        if amount <= 0:
            return 0.0

        default_issuer = getattr(cfg, "DEFAULT_ISSUER", DEFAULT_ISSUER)
        source = _resolve_asset(asset, default_issuer=default_issuer)
        base = _resolve_asset(base_asset, default_issuer=default_issuer)
        if source == base:
            return amount

        max_hops = int(getattr(cfg, "BASE_VALUE_MAX_HOPS", BASE_VALUE_MAX_HOPS))
        max_paths = int(getattr(cfg, "BASE_VALUE_MAX_PATHS", BASE_VALUE_MAX_PATHS))
        fee = float(getattr(cfg, "TRADING_FEE", TRADING_FEE))
        paths = _candidate_paths_to_target(
            graph,
            source=source,
            target=base,
            max_hops=max_hops,
            max_paths=max_paths,
        )
        if not paths:
            return 0.0

        best_out = 0.0
        for path in paths[:max_paths]:
            if len(path) < 2:
                continue
            sim = simulate_path(path, graph, amount, fee_fraction=fee)
            if sim.output_amount > best_out:
                best_out = sim.output_amount
        return best_out
    except Exception:
        return 0.0
