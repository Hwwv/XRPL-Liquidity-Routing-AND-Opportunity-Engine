"""
XRPL JSON-RPC client. Connects to Testnet or Devnet per config.
"""

import logging
from typing import Any

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import BookOffers
from xrpl.models.currencies import XRP, IssuedCurrency

from .config import get_json_rpc_url, BOOK_DEPTH

logger = logging.getLogger(__name__)


def _currency_to_xrpl(currency: str, issuer: str | None = None):
    """Build XRPL currency: XRP has no issuer."""
    if currency.upper() == "XRP":
        return XRP()
    if not issuer:
        raise ValueError(f"Issuer required for issued currency {currency}")
    return IssuedCurrency(currency=currency, issuer=issuer)


def get_client() -> JsonRpcClient:
    """Return a JsonRpcClient for the configured network."""
    url = get_json_rpc_url()
    logger.info("Using XRPL endpoint: %s", url)
    return JsonRpcClient(url)


def fetch_book_offers(
    client: JsonRpcClient,
    taker_gets_currency: str,
    taker_gets_issuer: str | None,
    taker_pays_currency: str,
    taker_pays_issuer: str | None,
    limit: int = BOOK_DEPTH,
) -> dict[str, Any]:
    """
    Request book_offers for a pair. Returns raw result with 'offers' list.
    taker_gets = what the taker receives, taker_pays = what the taker pays.
    """
    taker_gets = _currency_to_xrpl(taker_gets_currency, taker_gets_issuer)
    taker_pays = _currency_to_xrpl(taker_pays_currency, taker_pays_issuer)
    request = BookOffers(
        taker_gets=taker_gets,
        taker_pays=taker_pays,
        limit=limit,
    )
    response = client.request(request)
    result = response.result
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return dict(result) if result is not None else {}
