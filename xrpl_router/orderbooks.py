"""
Order book fetching and normalization to Level (rate, capacity).
XRP amounts are normalized from drops to XRP units.
"""

import logging
from dataclasses import dataclass
from typing import Any

from . import xrpl_client
from .config import BOOK_DEPTH, MAX_LEVELS_PER_EDGE

logger = logging.getLogger(__name__)

# 1 XRP = 1e6 drops
DROPS_PER_XRP = 1_000_000


@dataclass
class Level:
    """Single order book level: rate (dst per 1 src) and capacity (available src units)."""

    rate: float
    capacity: float


def _parse_amount(amount: Any) -> float:
    """
    Parse XRPL amount to float. XRP can be string drops (integer) or decimal.
    Issued currency is string decimal.
    """
    if isinstance(amount, (int, float)):
        return float(amount)
    if isinstance(amount, str):
        return float(amount)
    if isinstance(amount, dict):
        value = amount.get("value")
        if value is not None:
            return float(value)
        # XRP as dict sometimes has "value" in drops as string
        return float(amount.get("value", 0))
    return 0.0


def _amount_to_src_units(amount_raw: Any, is_xrp: bool) -> float:
    """Normalize amount to our units: XRP as XRP (not drops), issued as decimal."""
    if is_xrp:
        if isinstance(amount_raw, str):
            if "." in amount_raw:
                return float(amount_raw)
            return int(amount_raw) / DROPS_PER_XRP
        if isinstance(amount_raw, int):
            return amount_raw / DROPS_PER_XRP
        if isinstance(amount_raw, dict):
            return _parse_amount(amount_raw.get("value", 0)) / DROPS_PER_XRP
    return _parse_amount(amount_raw)


def offers_to_levels(
    offers: list[dict],
    taker_pays_is_xrp: bool,
    taker_gets_is_xrp: bool,
    max_levels: int = MAX_LEVELS_PER_EDGE,
) -> list[Level]:
    """
    Convert XRPL offers to Level list. Each offer: we pay taker_pays (src), get taker_gets (dst).
    rate = dst per 1 src = taker_gets / taker_pays.
    capacity = available src (taker_pays) we can use.
    """
    levels: list[Level] = []
    for offer in offers[:max_levels]:
        taker_gets = offer.get("TakerGets") or offer.get("taker_gets")
        taker_pays = offer.get("TakerPays") or offer.get("taker_pays")
        if not taker_gets or not taker_pays:
            continue
        # Funded amounts if present (partial fill)
        gets_funded = offer.get("taker_gets_funded") or taker_gets
        pays_funded = offer.get("taker_pays_funded") or taker_pays
        amount_gets = _amount_to_src_units(gets_funded, taker_gets_is_xrp)
        amount_pays = _amount_to_src_units(pays_funded, taker_pays_is_xrp)
        if amount_pays <= 0:
            continue
        rate = amount_gets / amount_pays  # dst per 1 src
        capacity = amount_pays  # available src
        levels.append(Level(rate=rate, capacity=capacity))
    return levels


def fetch_order_book(
    client,
    src_currency: str,
    src_issuer: str | None,
    dst_currency: str,
    dst_issuer: str | None,
    limit: int = BOOK_DEPTH,
) -> list[Level]:
    """
    Fetch order book for pair (src -> dst): we sell src, get dst.
    Uses book_offers with taker_pays=src, taker_gets=dst.
    """
    raw = xrpl_client.fetch_book_offers(
        client,
        taker_gets_currency=dst_currency,
        taker_gets_issuer=dst_issuer,
        taker_pays_currency=src_currency,
        taker_pays_issuer=src_issuer,
        limit=limit,
    )
    offers = raw.get("offers") or []
    src_is_xrp = src_currency.upper() == "XRP"
    dst_is_xrp = dst_currency.upper() == "XRP"
    return offers_to_levels(
        offers, taker_pays_is_xrp=src_is_xrp, taker_gets_is_xrp=dst_is_xrp
    )
