"""
Liquidity graph: directed multi-graph with capacity-limited edges.
graph: Dict[str, List[MarketEdge]], keyed by source currency.
"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .orderbooks import Level


@dataclass
class MarketEdge:
    """One directed edge: src -> dst with order book levels."""
    src: str
    dst: str
    levels: list["Level"] = field(default_factory=list)

    def best_rate(self) -> float | None:
        """Best (highest) rate at top level, or None if no levels."""
        if not self.levels:
            return None
        return self.levels[0].rate


def build_graph_from_pairs(
    pairs: list[tuple[str, str | None, str, str | None]],
    fetch_book_fn,
    client,
    limit_per_book: int = 20,
) -> dict[str, list[MarketEdge]]:
    """
    Build graph from list of (src_currency, src_issuer, dst_currency, dst_issuer).
    fetch_book_fn(client, src_cur, src_iss, dst_cur, dst_iss, limit) -> list[Level].
    """
    graph: dict[str, list[MarketEdge]] = {}
    for src_currency, src_issuer, dst_currency, dst_issuer in pairs:
        levels = fetch_book_fn(
            client, src_currency, src_issuer, dst_currency, dst_issuer, limit=limit_per_book
        )
        if not levels:
            continue
        src_key = _asset_key(src_currency, src_issuer)
        dst_key = _asset_key(dst_currency, dst_issuer)
        edge = MarketEdge(src=src_key, dst=dst_key, levels=levels)
        graph.setdefault(src_key, []).append(edge)
    return graph


def _asset_key(currency: str, issuer: str | None) -> str:
    """Canonical key for an asset (e.g. XRP vs USD:issuer)."""
    if currency.upper() == "XRP":
        return "XRP"
    return f"{currency.upper()}:{issuer or ''}"
