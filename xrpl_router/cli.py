"""
CLI: Mode A (route), Mode B (arbitrage), Mode C (greedy agent simulation).
"""
import argparse
import logging
import sys

from .config import (
    get_json_rpc_url,
    DEFAULT_BOOK_PAIRS,
    MAX_HOPS,
    MAX_PATHS,
    TRADING_FEE,
    BOOK_DEPTH,
    LOG_LEVEL,
    XRPL_NETWORK,
)
from . import xrpl_client
from .orderbooks import fetch_order_book
from .graph import build_graph_from_pairs
from .routing import dijkstra_best_path
from .simulate import simulate_path
from .arbitrage import scan_arbitrage
from .strategy import evaluate_routes, greedy_agent_step


def _asset_key(currency: str, issuer: str | None) -> str:
    if currency.upper() == "XRP":
        return "XRP"
    return f"{currency.upper()}:{issuer or ''}"


def _resolve_asset(s: str, default_issuer: str) -> str:
    """Resolve 'XRP' or 'USD' or 'USD:issuer' to asset key."""
    s = s.strip()
    if not s:
        return s
    if s.upper() == "XRP":
        return "XRP"
    if ":" in s:
        cur, iss = s.split(":", 1)
        return _asset_key(cur, iss.strip() or None)
    return _asset_key(s, default_issuer)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def _build_graph(client, pairs: list | None = None):
    pairs = pairs or DEFAULT_BOOK_PAIRS
    return build_graph_from_pairs(pairs, fetch_order_book, client, limit_per_book=BOOK_DEPTH)


def cmd_route(args: argparse.Namespace) -> int:
    """Mode A: Route optimization."""
    _setup_logging(args.verbose)
    from .config import DEFAULT_ISSUER
    client = xrpl_client.get_client()
    graph = _build_graph(client)
    source = _resolve_asset(args.source_asset, DEFAULT_ISSUER)
    target = _resolve_asset(args.target_asset, DEFAULT_ISSUER)
    amount = float(args.amount)
    if not graph:
        print("No order book data; cannot build graph.", file=sys.stderr)
        return 1
    result = dijkstra_best_path(graph, source, target)
    if result is None:
        print(f"No path from {source} to {target}.", file=sys.stderr)
        return 1
    sim = simulate_path(result.path, graph, amount, TRADING_FEE)
    print("Best Path:", " → ".join(result.path))
    print("Expected Output (no slippage):", f"{result.effective_rate * amount:.4f}")
    print("Simulated Output (with slippage/fees):", f"{sim.output_amount:.4f}")
    print("Effective Rate:", f"{sim.effective_rate:.4f}")
    return 0


def cmd_arbitrage(args: argparse.Namespace) -> int:
    """Mode B: Arbitrage scan."""
    _setup_logging(args.verbose)
    client = xrpl_client.get_client()
    graph = _build_graph(client)
    if not graph:
        print("No order book data; cannot build graph.", file=sys.stderr)
        return 1
    report = scan_arbitrage(graph, trial_amount=float(args.trial_amount or 1000))
    if report is None:
        print("No arbitrage cycle detected.")
        return 0
    print("Arbitrage Cycle Detected:")
    print("  ", " → ".join(report.cycle))
    print("  Estimated Profit:", f"{report.profit_pct:.2f}%")
    print("  Profit (absolute):", report.profit_absolute)
    print("  Confidence:", f"{report.confidence:.2f}")
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """Mode C: Greedy agent simulation."""
    _setup_logging(args.verbose)
    from .config import DEFAULT_ISSUER
    client = xrpl_client.get_client()
    graph = _build_graph(client)
    if not graph:
        print("No order book data; cannot build graph.", file=sys.stderr)
        return 1
    asset = _resolve_asset(args.asset, DEFAULT_ISSUER)
    amount = float(args.amount)
    steps = int(args.steps)
    portfolio: dict[str, float] = {asset: amount}
    growth: list[float] = [amount]
    for t in range(steps):
        choice, used = greedy_agent_step(
            graph, portfolio,
            fee_fraction=TRADING_FEE,
            max_hops=MAX_HOPS,
            max_paths=MAX_PATHS,
        )
        if choice is None or used == "" or choice.expected_value <= 0:
            break
        amt = portfolio.get(used, 0)
        if amt <= 0:
            break
        portfolio[used] = 0.0
        dest = choice.path[-1]
        portfolio[dest] = portfolio.get(dest, 0) + choice.output_amount
        total = sum(portfolio.values())
        growth.append(total)
    total_value = sum(portfolio.values())
    print("Final Portfolio:", portfolio)
    print("Final Portfolio Value:", f"{total_value:.2f}")
    if len(growth) > 1:
        returns = (growth[-1] - growth[0]) / growth[0] if growth[0] else 0
        print("Growth Curve (value per step):", [round(g, 2) for g in growth])
        print("Total Return:", f"{returns:.2%}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="XRPL Liquidity Routing & Opportunity Engine")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    sub = parser.add_subparsers(dest="command", required=True)

    route_p = sub.add_parser("route", help="Mode A: Find best route from source to target")
    route_p.add_argument("--from", dest="source_asset", required=True, metavar="ASSET", help="Source asset (e.g. XRP, USD)")
    route_p.add_argument("--to", dest="target_asset", required=True, metavar="ASSET", help="Target asset")
    route_p.add_argument("--amount", type=float, default=100.0, help="Amount to convert")
    route_p.set_defaults(func=cmd_route)

    arb_p = sub.add_parser("arbitrage", help="Mode B: Scan for arbitrage cycles")
    arb_p.add_argument("--trial-amount", type=float, default=1000, help="Trial amount for profit estimate")
    arb_p.set_defaults(func=cmd_arbitrage)

    sim_p = sub.add_parser("simulate", help="Mode C: Greedy agent simulation")
    sim_p.add_argument("--asset", default="XRP", help="Initial asset")
    sim_p.add_argument("--amount", type=float, default=1000, help="Initial amount")
    sim_p.add_argument("--steps", type=int, default=20, help="Time steps")
    sim_p.set_defaults(func=cmd_simulate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
