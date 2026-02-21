"""
Opportunity evaluation and greedy policy using base-asset scoring.
"""

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

from . import config as config_module
from .graph import Asset, MarketEdge
from .simulate import compute_success_probability, simulate_path
from .valuation import value_in_base

logger = logging.getLogger(__name__)


def _resolve_asset(s: str | Asset) -> Asset:
    if isinstance(s, Asset):
        return s
    s = (s or "").strip()
    if not s:
        return Asset("XRP", None)
    if s.upper() == "XRP":
        return Asset("XRP", None)
    if ":" in s:
        cur, iss = s.split(":", 1)
        return Asset(cur.upper(), iss.strip() or None)
    return Asset(s.upper(), config_module.DEFAULT_ISSUER)


@dataclass
class RouteChoice:
    """Best route choice for one source asset."""

    path: list[Asset]
    expected_value: float
    output_amount: float
    success_probability: float
    effective_rate: float
    score: float
    ev_gain_ratio: float
    input_amount: float
    base_before: float = 0.0
    base_after: float = 0.0
    gain_mult: float = 0.0
    hold_reason: str = ""
    action: str = "TRADE"


@dataclass
class AgentState:
    """Minimal state required for cooldown/reversal blocking."""

    last_trade_step: int = -(10**9)
    last_from_asset: Asset | None = None
    last_to_asset: Asset | None = None


def generate_candidate_paths(
    graph: dict[Asset, list[MarketEdge]],
    source: Asset,
    max_hops: int = config_module.MAX_HOPS,
    max_paths: int = config_module.MAX_PATHS,
) -> list[list[Asset]]:
    """
    Generate candidate paths from source with length in [2, max_hops+1].
    Uses BFS; returns up to max_paths paths (prefer shorter, then by destination).
    """
    if source not in graph:
        return []
    paths: list[list[Asset]] = []
    queue: deque[tuple[Asset, list[Asset]]] = deque([(source, [source])])
    seen: set[tuple[Asset, ...]] = set()
    while queue and len(paths) < max_paths * 4:
        node, path = queue.popleft()
        if len(path) >= 2:
            paths.append(path[:])
        if len(path) > max_hops:
            continue
        for edge in graph.get(node, []):
            if edge.dst in path:
                continue
            key = tuple(path + [edge.dst])
            if key in seen:
                continue
            seen.add(key)
            queue.append((edge.dst, path + [edge.dst]))
    paths.sort(key=lambda p: (len(p), str(p[-1])))
    return paths[:max_paths]


def evaluate_route_candidates(
    graph: dict[Asset, list[MarketEdge]],
    source: Asset,
    amount: float,
    fee_fraction: float = config_module.TRADING_FEE,
    max_hops: int = config_module.MAX_HOPS,
    max_paths: int = config_module.MAX_PATHS,
    cfg: Any = config_module,
) -> list[RouteChoice]:
    """
    Evaluate candidate routes from source and include a HOLD baseline candidate.
    Candidates are sorted descending by gain multiple.
    """
    source = _resolve_asset(source)
    amount = float(amount)
    base_before = value_in_base(source, amount, cfg.BASE_ASSET, graph, cfg)
    candidates: list[RouteChoice] = []

    hold_gain = 1.0
    candidates.append(
        RouteChoice(
            path=[source],
            expected_value=base_before,
            output_amount=amount,
            success_probability=1.0,
            effective_rate=1.0,
            score=hold_gain,
            ev_gain_ratio=hold_gain,
            input_amount=amount,
            base_before=base_before,
            base_after=base_before,
            gain_mult=hold_gain,
            hold_reason="baseline hold",
            action="HOLD",
        )
    )

    for path in generate_candidate_paths(
        graph, source, max_hops=max_hops, max_paths=max_paths
    ):
        if len(path) < 2:
            continue
        sim = simulate_path(path, graph, amount, fee_fraction=fee_fraction)
        if sim.output_amount <= 0:
            continue
        dst_asset = path[-1]
        base_after = value_in_base(
            dst_asset, sim.output_amount, cfg.BASE_ASSET, graph, cfg
        )
        gain_mult = (base_after / base_before) if base_before > 0 else 0.0
        p_success = compute_success_probability(path, graph, amount)
        candidates.append(
            RouteChoice(
                path=path,
                expected_value=base_after,
                output_amount=sim.output_amount,
                success_probability=p_success,
                effective_rate=sim.effective_rate,
                score=gain_mult,
                ev_gain_ratio=gain_mult,
                input_amount=amount,
                base_before=base_before,
                base_after=base_after,
                gain_mult=gain_mult,
                action="TRADE",
            )
        )

    candidates.sort(
        key=lambda c: (c.gain_mult, c.base_after, c.output_amount), reverse=True
    )
    return candidates


def evaluate_routes(
    graph: dict[Asset, list[MarketEdge]],
    source: Asset,
    amount: float,
    fee_fraction: float = config_module.TRADING_FEE,
    risk_penalty: float = config_module.RISK_PENALTY,
    success_probability: float | None = None,
    max_hops: int = config_module.MAX_HOPS,
    max_paths: int = config_module.MAX_PATHS,
    cfg: Any = config_module,
    strategy_mode: str = "base",
) -> RouteChoice | None:
    """
    Return highest-scoring candidate route (including HOLD baseline).
    """
    if strategy_mode == "legacy":
        return evaluate_routes_legacy(
            graph,
            source,
            amount,
            fee_fraction=fee_fraction,
            max_hops=max_hops,
            max_paths=max_paths,
        )
    del risk_penalty, success_probability
    candidates = evaluate_route_candidates(
        graph,
        source,
        amount,
        fee_fraction=fee_fraction,
        max_hops=max_hops,
        max_paths=max_paths,
        cfg=cfg,
    )
    return candidates[0] if candidates else None


def evaluate_routes_legacy(
    graph: dict[Asset, list[MarketEdge]],
    source: Asset,
    amount: float,
    fee_fraction: float = config_module.TRADING_FEE,
    max_hops: int = config_module.MAX_HOPS,
    max_paths: int = config_module.MAX_PATHS,
) -> RouteChoice | None:
    """
    Original EV-based route scoring kept for A/B comparison.
    """
    source = _resolve_asset(source)
    best: RouteChoice | None = None
    for path in generate_candidate_paths(
        graph, source, max_hops=max_hops, max_paths=max_paths
    ):
        if len(path) < 2:
            continue
        p_success = compute_success_probability(path, graph, amount)
        sim = simulate_path(path, graph, amount, fee_fraction)
        ev = (
            p_success * sim.output_amount
            - (1 - p_success) * config_module.FAILURE_PENALTY
        )
        hop_count = len(path) - 1
        score = (
            ev
            - config_module.LAMBDA_HOPS * hop_count
            - config_module.LAMBDA_SPREAD * 0.0
            - config_module.LAMBDA_DEPTH * 0.0
        )
        ev_gain_ratio = ev / amount if amount > 0 else 0.0
        candidate = RouteChoice(
            path=path,
            expected_value=ev,
            output_amount=sim.output_amount,
            success_probability=p_success,
            effective_rate=sim.effective_rate,
            score=score,
            ev_gain_ratio=ev_gain_ratio,
            input_amount=amount,
            base_before=amount,
            base_after=ev,
            gain_mult=ev_gain_ratio,
            action="TRADE",
        )
        if best is None or candidate.score > best.score:
            best = candidate
    return best


def greedy_agent_step_legacy(
    graph: dict[Asset, list[MarketEdge]],
    portfolio: dict[Any, float],
    fee_fraction: float = config_module.TRADING_FEE,
    max_hops: int = config_module.MAX_HOPS,
    max_paths: int = config_module.MAX_PATHS,
    last_asset: Asset | None = None,
) -> tuple[RouteChoice | None, Any]:
    """
    Original greedy policy with EV threshold and optional reversal guard.
    """
    best: RouteChoice | None = None
    asset_used: Any = ""
    for asset_key, balance in portfolio.items():
        if balance <= 0:
            continue
        asset = _resolve_asset(asset_key)
        choice = evaluate_routes_legacy(
            graph,
            asset,
            balance,
            fee_fraction=fee_fraction,
            max_hops=max_hops,
            max_paths=max_paths,
        )
        if choice is None or choice.score <= 0:
            continue

        if (
            config_module.ENABLE_REVERSAL_GUARD
            and last_asset is not None
            and choice.path[-1] == last_asset
        ):
            reversal_threshold = balance * config_module.REVERSE_MIN_EV_MULTIPLIER
            if choice.expected_value < reversal_threshold:
                continue

        hold_threshold = balance * config_module.MIN_EV_MULTIPLIER
        if choice.expected_value < hold_threshold:
            continue

        if best is None or choice.score > best.score:
            best = choice
            asset_used = asset_key

    return (best, asset_used) if best is not None else (None, "")


def greedy_agent_step(
    graph: dict[Asset, list[MarketEdge]],
    portfolio: dict[Any, float],
    fee_fraction: float = config_module.TRADING_FEE,
    max_hops: int = config_module.MAX_HOPS,
    max_paths: int = config_module.MAX_PATHS,
    last_asset: Asset | None = None,
    step: int = 0,
    state: AgentState | None = None,
    cfg: Any = config_module,
    strategy_mode: str = "base",
) -> tuple[RouteChoice | None, Any]:
    """
    Pick one action for the portfolio at this step.
    Returns (trade_choice, portfolio_key_used). HOLD returns (None, "").
    """
    if strategy_mode == "legacy":
        return greedy_agent_step_legacy(
            graph,
            portfolio,
            fee_fraction=fee_fraction,
            max_hops=max_hops,
            max_paths=max_paths,
            last_asset=last_asset,
        )

    if state is None:
        state = AgentState()
    if last_asset is not None and state.last_from_asset is None:
        state.last_from_asset = last_asset

    best_trade: RouteChoice | None = None
    best_used_key: Any = ""
    best_src_asset: Asset | None = None
    best_hold: RouteChoice | None = None
    best_hold_src: tuple[str, float] | None = None
    hold_reasons: list[str] = []

    for asset_key, balance in portfolio.items():
        if balance <= 0:
            continue
        src_asset = _resolve_asset(asset_key)
        candidates = evaluate_route_candidates(
            graph,
            src_asset,
            balance,
            fee_fraction=fee_fraction,
            max_hops=max_hops,
            max_paths=max_paths,
            cfg=cfg,
        )
        if not candidates:
            hold_reasons.append("no candidates")
            continue

        src_best_hold = next((c for c in candidates if c.action == "HOLD"), None)
        if src_best_hold is not None:
            if best_hold is None or src_best_hold.base_after > best_hold.base_after:
                best_hold = src_best_hold
                best_hold_src = (str(src_asset), balance)

        src_trade_selected: RouteChoice | None = None
        for cand in candidates:
            if cand.action != "TRADE":
                continue

            reverse_blocked = (
                cfg.REVERSE_BLOCK
                and state.last_trade_step >= 0
                and (step - state.last_trade_step) < int(cfg.COOLDOWN_STEPS)
                and state.last_from_asset is not None
                and cand.path[-1] == state.last_from_asset
            )
            if reverse_blocked:
                hold_reasons.append("reversal blocked")
                continue
            if cand.gain_mult < float(cfg.MIN_BASE_GAIN_MULT):
                hold_reasons.append("below threshold")
                continue
            src_trade_selected = cand
            break

        if src_trade_selected is None:
            continue

        if best_trade is None or src_trade_selected.gain_mult > best_trade.gain_mult:
            best_trade = src_trade_selected
            best_used_key = asset_key
            best_src_asset = src_asset

    if best_trade is None:
        reason = "no candidates"
        if hold_reasons:
            if "below threshold" in hold_reasons:
                reason = "below threshold"
            elif "reversal blocked" in hold_reasons:
                reason = "reversal blocked"
        ctx_asset = best_hold_src[0] if best_hold_src else ""
        ctx_amount = best_hold_src[1] if best_hold_src else 0.0
        base_before = best_hold.base_before if best_hold else 0.0
        logger.info(
            "step=%s asset=%s amount=%.6f action=HOLD base_before=%.6f base_after=%.6f gain_mult=%.6f reason=%s",
            step,
            ctx_asset,
            ctx_amount,
            base_before,
            base_before,
            1.0 if base_before > 0 else 0.0,
            reason,
        )
        return None, ""

    state.last_trade_step = step
    state.last_from_asset = best_src_asset
    state.last_to_asset = best_trade.path[-1]
    logger.info(
        "step=%s asset=%s amount=%.6f action=TRADE path=%s base_before=%.6f base_after=%.6f gain_mult=%.6f",
        step,
        str(best_src_asset),
        best_trade.input_amount,
        " -> ".join(str(p) for p in best_trade.path),
        best_trade.base_before,
        best_trade.base_after,
        best_trade.gain_mult,
    )
    return best_trade, best_used_key
