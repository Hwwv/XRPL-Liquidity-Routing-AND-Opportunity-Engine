"""
Unified graph loading: live XRPL or mock (for testing and UI without network).
"""

from typing import Any

from .config import DEFAULT_BOOK_PAIRS, BOOK_DEPTH
from .graph import build_graph_from_pairs
from .orderbooks import fetch_order_book
from . import mock_data


def get_graph(use_mock: bool = False, pairs: list | None = None) -> dict:
    """
    Return the liquidity graph. No network calls if use_mock=True.
    """
    if use_mock:
        return mock_data.get_mock_graph(limit_per_book=BOOK_DEPTH)
    from . import xrpl_client

    client = xrpl_client.get_client()
    pairs = pairs or DEFAULT_BOOK_PAIRS
    return build_graph_from_pairs(
        pairs, fetch_order_book, client, limit_per_book=BOOK_DEPTH
    )
