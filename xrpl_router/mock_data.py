"""
Mock order books and graph for full-stack testing without live XRPL.
Deterministic data: same graph every time for route, arbitrage, and simulate tests.
"""
from .orderbooks import Level
from .graph import MarketEdge, build_graph_from_pairs
from .config import DEFAULT_BOOK_PAIRS, DEFAULT_ISSUER, BOOK_DEPTH


def _asset_key(currency: str, issuer: str | None) -> str:
    if currency.upper() == "XRP":
        return "XRP"
    return f"{currency.upper()}:{issuer or ''}"


# Deterministic mock books: (src_key, dst_key) -> list of (rate, capacity)
# Rates chosen so no arbitrage: all cycles have product < 1 (e.g. USD->EUR 0.9, EUR->USD 1.05 => 0.945).
_MOCK_BOOKS: dict[tuple[str, str], list[tuple[float, float]]] = {
    ("XRP", f"USD:{DEFAULT_ISSUER}"): [(2.0, 1000.0), (1.95, 2000.0)],
    (f"USD:{DEFAULT_ISSUER}", "XRP"): [(0.48, 5000.0), (0.45, 3000.0)],
    ("XRP", f"EUR:{DEFAULT_ISSUER}"): [(1.8, 800.0), (1.75, 1500.0)],
    (f"EUR:{DEFAULT_ISSUER}", "XRP"): [(0.52, 5000.0), (0.50, 2000.0)],
    (f"USD:{DEFAULT_ISSUER}", f"EUR:{DEFAULT_ISSUER}"): [(0.90, 3000.0), (0.88, 2000.0)],
    (f"EUR:{DEFAULT_ISSUER}", f"USD:{DEFAULT_ISSUER}"): [(1.05, 3000.0), (1.03, 2000.0)],
}


def mock_fetch_order_book(
    client: object,
    src_currency: str,
    src_issuer: str | None,
    dst_currency: str,
    dst_issuer: str | None,
    limit: int = BOOK_DEPTH,
) -> list[Level]:
    """
    Return deterministic order book levels for the given pair.
    Same signature as orderbooks.fetch_order_book so it can replace it in build_graph_from_pairs.
    """
    src_key = _asset_key(src_currency, src_issuer)
    dst_key = _asset_key(dst_currency, dst_issuer)
    pairs = _MOCK_BOOKS.get((src_key, dst_key), [])
    levels = [Level(rate=r, capacity=c) for r, c in pairs[:limit]]
    return levels


def get_mock_graph(limit_per_book: int = BOOK_DEPTH) -> dict[str, list[MarketEdge]]:
    """
    Build the liquidity graph from mock order books only (no network).
    Uses same pair list as live (DEFAULT_BOOK_PAIRS) so asset keys match.
    """
    # client is ignored by mock_fetch_order_book
    return build_graph_from_pairs(
        DEFAULT_BOOK_PAIRS,
        mock_fetch_order_book,
        client=None,
        limit_per_book=limit_per_book,
    )


# --- Mock graph with an arbitrage cycle (for testing) ---
# Keys must match graph._asset_key: "A:" for (A, None), "B:" for (B, ""), etc.
# A -> B 2.0, B -> C 1.1, C -> A 0.5 => product 1.1 > 1 => negative cycle
_MOCK_BOOKS_ARBITRAGE: dict[tuple[str, str], list[tuple[float, float]]] = {
    ("A:", "B:"): [(2.0, 10000.0)],
    ("B:", "C:"): [(1.1, 10000.0)],
    ("C:", "A:"): [(0.5, 10000.0)],
}


def _mock_fetch_arbitrage(
    client: object,
    src_currency: str,
    src_issuer: str | None,
    dst_currency: str,
    dst_issuer: str | None,
    limit: int = 20,
) -> list[Level]:
    src_key = _asset_key(src_currency, src_issuer)
    dst_key = _asset_key(dst_currency, dst_issuer)
    pairs = _MOCK_BOOKS_ARBITRAGE.get((src_key, dst_key), [])
    return [Level(rate=r, capacity=c) for r, c in pairs[:limit]]


def get_mock_graph_with_arbitrage(limit_per_book: int = 20) -> dict[str, list[MarketEdge]]:
    """Mock graph that contains a negative cycle (for arbitrage tests)."""
    return build_graph_from_pairs(
        [("A", None, "B", ""), ("B", "", "C", None), ("C", None, "A", "")],
        _mock_fetch_arbitrage,
        client=None,
        limit_per_book=limit_per_book,
    )
