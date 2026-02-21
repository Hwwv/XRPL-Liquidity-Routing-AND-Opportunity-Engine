"""
Configuration for XRPL Liquidity Routing & Opportunity Engine.
Supports Testnet and Devnet via XRPL_NETWORK env var.
"""

import os
from typing import Literal

# --- Network (developer environments) ---
# Set XRPL_NETWORK=testnet (default) or XRPL_NETWORK=devnet
XRPL_NETWORK: Literal["testnet", "devnet"] = os.environ.get(
    "XRPL_NETWORK", "testnet"
).lower()
if XRPL_NETWORK not in ("testnet", "devnet"):
    XRPL_NETWORK = "testnet"

# JSON-RPC endpoints (public)
TESTNET_JSON_RPC = "https://s.altnet.rippletest.net:51234"
DEVNET_JSON_RPC = "https://s.devnet.rippletest.net:51234"


def get_json_rpc_url() -> str:
    """Return the JSON-RPC URL for the current network (reads XRPL_NETWORK env each time)."""
    net = os.environ.get("XRPL_NETWORK", "testnet").lower()
    if net not in ("testnet", "devnet"):
        net = "testnet"
    return DEVNET_JSON_RPC if net == "devnet" else TESTNET_JSON_RPC


# --- Routing & strategy ---
MAX_HOPS: int = 3
MAX_PATHS: int = 5
TRADING_FEE: float = 0.001  # per-hop fee as fraction (e.g. 0.001 = 0.1%)
RISK_PENALTY: float = 0.002  # penalty for execution uncertainty

# --- Order book ---
BOOK_DEPTH: int = 20  # max levels per book (limit for book_offers)
MAX_LEVELS_PER_EDGE: int = 20  # cap levels per edge when building graph

# --- Simulation ---
DEFAULT_SUCCESS_PROBABILITY: float = 0.95  # heuristic P(success) when not estimated
FAILURE_PENALTY: float = 0.0  # penalty for failed trades (set to input amount or 0)

# --- Risk-aware scoring ---
LAMBDA_HOPS: float = 0.01  # penalty per hop
LAMBDA_SPREAD: float = 0.1  # penalty for spread
LAMBDA_DEPTH: float = 0.05  # penalty for thin liquidity

# --- Greedy agent anti-churn controls ---
MIN_EV_MULTIPLIER: float = (
    1.002  # require +0.2% improvement over HOLD to trade (1.002 = +0.2%)
)
REVERSE_MIN_EV_MULTIPLIER: float = (
    1.01  # require +1% to execute immediate reversal (optional guard)
)
ENABLE_REVERSAL_GUARD: bool = (
    False  # set True to prevent immediate back-and-forth trading
)

# --- Base-asset scoring + cooldown controls ---
BASE_ASSET = "USD"  # can be "XRP", "USD", "USD:rIssuer", or Asset(...)
MIN_BASE_GAIN_MULT: float = 1.002
COOLDOWN_STEPS: int = 2
REVERSE_BLOCK: bool = True
BASE_VALUE_MAX_HOPS: int = 3
BASE_VALUE_MAX_PATHS: int = 3

# --- Strategy mode / lookahead controls ---
STRATEGY_MODE: str = "greedy"  # "legacy" | "greedy" | "extended-greedy"
LOOKAHEAD_DEPTH: int = 2  # fixed at 2 in this version
LOOKAHEAD_TOPK: int = 5
LOOKAHEAD_MIN_GAIN_MULT: float = (
    1.002  # retained for compatibility; MIN_BASE_GAIN_MULT is used
)
LOOKAHEAD_MAX_HOPS: int = 3
LOOKAHEAD_MAX_PATHS: int = 5

# --- Default order book pairs (src_currency, src_issuer, dst_currency, dst_issuer) ---
# Testnet/Devnet common gateway issuer (ripple.com)
DEFAULT_ISSUER = "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B"
# Pairs to fetch for graph: both directions
DEFAULT_BOOK_PAIRS: list[tuple[str, str | None, str, str | None]] = [
    ("XRP", None, "USD", DEFAULT_ISSUER),
    ("USD", DEFAULT_ISSUER, "XRP", None),
    ("XRP", None, "EUR", DEFAULT_ISSUER),
    ("EUR", DEFAULT_ISSUER, "XRP", None),
    ("USD", DEFAULT_ISSUER, "EUR", DEFAULT_ISSUER),
    ("EUR", DEFAULT_ISSUER, "USD", DEFAULT_ISSUER),
]
