"""
XRPL Liquidity Routing & Opportunity Engine.
"""
from .config import (
    XRPL_NETWORK,
    get_json_rpc_url,
    MAX_HOPS,
    MAX_PATHS,
    TRADING_FEE,
    RISK_PENALTY,
    BOOK_DEPTH,
    DEFAULT_BOOK_PAIRS,
)
from .orderbooks import Level, fetch_order_book
from .graph import MarketEdge, build_graph_from_pairs
from .routing import dijkstra_best_path, bellman_ford_negative_cycle, PathResult
from .simulate import simulate_path, SimResult
from .arbitrage import scan_arbitrage, ArbitrageReport
from .strategy import evaluate_routes, greedy_agent_step, RouteChoice

__all__ = [
    "XRPL_NETWORK",
    "get_json_rpc_url",
    "MAX_HOPS",
    "MAX_PATHS",
    "TRADING_FEE",
    "RISK_PENALTY",
    "BOOK_DEPTH",
    "DEFAULT_BOOK_PAIRS",
    "Level",
    "fetch_order_book",
    "MarketEdge",
    "build_graph_from_pairs",
    "dijkstra_best_path",
    "bellman_ford_negative_cycle",
    "PathResult",
    "simulate_path",
    "SimResult",
    "scan_arbitrage",
    "ArbitrageReport",
    "evaluate_routes",
    "greedy_agent_step",
    "RouteChoice",
]
