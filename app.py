#!/usr/bin/env python3
"""
Streamlit UI for XRPL Liquidity Routing & Opportunity Engine.
Run from project root: streamlit run app.py

All Streamlit calls live in this file so ScriptRunContext is set correctly.
"""
import sys
import os
import warnings
import logging
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress Streamlit warnings when run in bare mode
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message=".*Session state does not function.*")
warnings.filterwarnings("ignore", message=".*to view this Streamlit app on a browser.*")

# Suppress Streamlit logging warnings
logging.getLogger("streamlit").setLevel(logging.ERROR)

from xrpl_router import config as router_cfg
from xrpl_router.config import DEFAULT_ISSUER, TRADING_FEE, MAX_HOPS, MAX_PATHS
from xrpl_router.graph import Asset
from xrpl_router.loader import get_graph
from xrpl_router.routing import dijkstra_best_path
from xrpl_router.simulate import simulate_path
from xrpl_router.arbitrage import scan_arbitrage
from xrpl_router.valuation import value_in_base
from xrpl_router.strategy import (
    AgentState,
    STRATEGY_EXTENDED_GREEDY,
    STRATEGY_GREEDY,
    STRATEGY_LEGACY,
    greedy_agent_step,
    normalize_strategy_mode,
)

import streamlit as st


def generate_graph_dot(graph: dict, path: list = None) -> str:
    """Generate GraphViz DOT string for the liquidity graph, highlighting the path if provided."""
    dot_lines = ["digraph LiquidityGraph {"]
    dot_lines.append("  rankdir=LR;")  # Left to right layout
    dot_lines.append("  node [shape=circle];")

    # Collect all nodes
    nodes = set(graph.keys())
    for edges in graph.values():
        for edge in edges:
            nodes.add(edge.dst)

    # Add nodes
    for node in sorted(nodes, key=str):
        dot_lines.append(f'  "{node}" [label="{node}"];')

    # Add edges
    path_edges = set()
    if path:
        for i in range(len(path) - 1):
            path_edges.add((path[i], path[i + 1]))

    for from_asset, edges in graph.items():
        for edge in edges:
            to_asset = edge.dst
            rate = edge.best_rate()
            if rate is not None:
                label = f"{rate:.4f} (fee:{TRADING_FEE:.4f})"
                color = "red" if (from_asset, to_asset) in path_edges else "black"
                penwidth = "3" if (from_asset, to_asset) in path_edges else "1"
                dot_lines.append(
                    f'  "{from_asset}" -> "{to_asset}" [label="{label}", color={color}, penwidth={penwidth}];'
                )

    dot_lines.append("}")
    return "\n".join(dot_lines)


def _asset_key(currency: str, issuer: str | None) -> str:
    if currency.upper() == "XRP":
        return "XRP"
    return f"{currency.upper()}:{issuer or ''}"


def _resolve_asset(s: str) -> Asset:
    s = (s or "").strip()
    if not s:
        return Asset("XRP", None)
    if s.upper() == "XRP":
        return Asset("XRP", None)
    if ":" in s:
        cur, iss = s.split(":", 1)
        return Asset(cur.upper(), iss.strip() or None)
    return Asset(s.upper(), DEFAULT_ISSUER)


def _strategy_selector(key_prefix: str = "") -> str:
    labels = ["Legacy Greedy (EV)", "Greedy", "Extended-Greedy (2-step lookahead)"]
    label_to_mode = {
        "Legacy Greedy (EV)": STRATEGY_LEGACY,
        "Greedy": STRATEGY_GREEDY,
        "Extended-Greedy (2-step lookahead)": STRATEGY_EXTENDED_GREEDY,
    }
    normalized_default = normalize_strategy_mode(router_cfg.STRATEGY_MODE)
    default_label = (
        "Extended-Greedy (2-step lookahead)"
        if normalized_default == STRATEGY_EXTENDED_GREEDY
        else (
            "Legacy Greedy (EV)" if normalized_default == STRATEGY_LEGACY else "Greedy"
        )
    )
    selected_label = st.selectbox(
        "Strategy",
        options=labels,
        index=labels.index(default_label),
        key=f"{key_prefix}strategy",
    )
    return label_to_mode[selected_label]


def _build_strategy_cfg(key_prefix: str = ""):
    with st.expander("Strategy Settings", expanded=False):
        base_asset = st.text_input(
            "Base asset",
            value=str(router_cfg.BASE_ASSET),
            key=f"{key_prefix}base_asset",
            help="Reference asset for scoring, e.g. XRP, USD, or USD:rIssuer",
        )
        min_base_gain_mult = st.number_input(
            "Min base gain multiplier",
            min_value=1.0,
            value=float(router_cfg.MIN_BASE_GAIN_MULT),
            step=0.0005,
            format="%.4f",
            key=f"{key_prefix}min_base_gain_mult",
        )
        cooldown_steps = st.number_input(
            "Cooldown steps",
            min_value=0,
            value=int(router_cfg.COOLDOWN_STEPS),
            step=1,
            key=f"{key_prefix}cooldown_steps",
        )
        reverse_block = st.checkbox(
            "Block immediate reversal during cooldown",
            value=bool(router_cfg.REVERSE_BLOCK),
            key=f"{key_prefix}reverse_block",
        )
        base_value_max_hops = st.number_input(
            "Base valuation max hops",
            min_value=1,
            value=int(router_cfg.BASE_VALUE_MAX_HOPS),
            step=1,
            key=f"{key_prefix}base_value_max_hops",
        )
        base_value_max_paths = st.number_input(
            "Base valuation max paths",
            min_value=1,
            value=int(router_cfg.BASE_VALUE_MAX_PATHS),
            step=1,
            key=f"{key_prefix}base_value_max_paths",
        )
        lookahead_topk = st.number_input(
            "Lookahead top-K",
            min_value=1,
            value=int(router_cfg.LOOKAHEAD_TOPK),
            step=1,
            key=f"{key_prefix}lookahead_topk",
        )
        lookahead_max_hops = st.number_input(
            "Lookahead max hops",
            min_value=1,
            value=int(router_cfg.LOOKAHEAD_MAX_HOPS),
            step=1,
            key=f"{key_prefix}lookahead_max_hops",
        )
        lookahead_max_paths = st.number_input(
            "Lookahead max paths",
            min_value=1,
            value=int(router_cfg.LOOKAHEAD_MAX_PATHS),
            step=1,
            key=f"{key_prefix}lookahead_max_paths",
        )
    return SimpleNamespace(
        DEFAULT_ISSUER=router_cfg.DEFAULT_ISSUER,
        TRADING_FEE=router_cfg.TRADING_FEE,
        BASE_ASSET=base_asset,
        MIN_BASE_GAIN_MULT=float(min_base_gain_mult),
        COOLDOWN_STEPS=int(cooldown_steps),
        REVERSE_BLOCK=bool(reverse_block),
        BASE_VALUE_MAX_HOPS=int(base_value_max_hops),
        BASE_VALUE_MAX_PATHS=int(base_value_max_paths),
        LOOKAHEAD_TOPK=int(lookahead_topk),
        LOOKAHEAD_DEPTH=int(router_cfg.LOOKAHEAD_DEPTH),
        LOOKAHEAD_MIN_GAIN_MULT=float(router_cfg.LOOKAHEAD_MIN_GAIN_MULT),
        LOOKAHEAD_MAX_HOPS=int(lookahead_max_hops),
        LOOKAHEAD_MAX_PATHS=int(lookahead_max_paths),
    )


# --- Streamlit app (single entrypoint so context is correct) ---
st.set_page_config(page_title="XRPL Router", layout="wide")
st.title("XRPL Liquidity Routing & Opportunity Engine")
st.caption(
    "Route optimization, arbitrage scan, and greedy agent simulation (paper trading only)."
)

use_mock = st.sidebar.checkbox(
    "Use mock data (no network)",
    value=True,
    help="Deterministic data for testing without XRPL.",
)
mode = st.sidebar.radio(
    "Mode",
    ["Route", "Arbitrage", "Simulate", "Visualization", "Comparison"],
    horizontal=True,
)

if mode == "Route":
    st.header("Route optimization")
    col1, col2, col3 = st.columns(3)
    with col1:
        source = st.text_input("From asset", value="XRP", help="e.g. XRP, USD, EUR")
    with col2:
        target = st.text_input("To asset", value="USD", help="e.g. XRP, USD, EUR")
    with col3:
        amount = st.number_input("Amount", min_value=0.01, value=100.0, step=10.0)
    if st.button("Find best route"):
        with st.spinner("Building graph..."):
            graph = get_graph(use_mock=use_mock)
        if not graph:
            st.error(
                "No order book data. Try live data (uncheck mock) or check network."
            )
        else:
            src = _resolve_asset(source)
            tgt = _resolve_asset(target)
            result = dijkstra_best_path(graph, src, tgt)
            if result is None:
                st.warning(f"No path from {source} to {target}.")
            else:
                sim = simulate_path(result.path, graph, amount, TRADING_FEE)
                st.success(
                    "Best path: **" + " → ".join(str(p) for p in result.path) + "**"
                )
                st.metric(
                    "Expected output (no slippage)",
                    f"{result.effective_rate * amount:.4f}",
                )
                st.metric(
                    "Simulated output (slippage + fees)", f"{sim.output_amount:.4f}"
                )
                st.metric("Effective rate", f"{sim.effective_rate:.4f}")

elif mode == "Arbitrage":
    st.header("Arbitrage scan")
    trial_amount = st.number_input(
        "Trial amount", min_value=1.0, value=1000.0, step=100.0
    )
    if st.button("Scan for arbitrage"):
        with st.spinner("Building graph and running Bellman-Ford..."):
            graph = get_graph(use_mock=use_mock)
        if not graph:
            st.error("No order book data.")
        else:
            report = scan_arbitrage(
                graph, trial_amount=trial_amount, fee_fraction=TRADING_FEE
            )
            if report is None:
                st.info("No arbitrage cycle detected.")
            else:
                st.success("Arbitrage cycle detected")
                st.write("Cycle:", " → ".join(report.cycle))
                st.metric("Estimated profit %", f"{report.profit_pct:.2f}%")
                st.metric("Profit (absolute)", f"{report.profit_absolute:.2f}")
                st.metric("Confidence", f"{report.confidence:.2f}")

elif mode == "Simulate":
    st.header("Greedy agent simulation")
    col1, col2, col3 = st.columns(3)
    with col1:
        asset = st.text_input("Initial asset", value="XRP")
    with col2:
        amount = st.number_input(
            "Initial amount", min_value=0.01, value=1000.0, step=100.0
        )
    with col3:
        steps = st.number_input("Steps", min_value=1, value=20, step=1)
    strategy_mode = _strategy_selector("sim_")
    strategy_cfg = _build_strategy_cfg("sim_")
    if st.button("Run simulation"):
        with st.spinner("Running greedy agent..."):
            graph = get_graph(use_mock=use_mock)
        if not graph:
            st.error("No order book data.")
        else:
            a = _resolve_asset(asset)
            portfolio = {a: amount}
            growth = [amount]
            debug_logs = []
            hold_count = 0
            trade_count = 0
            state = AgentState()
            last_asset = None

            for step in range(steps - 1):
                choice, used = greedy_agent_step(
                    graph,
                    portfolio,
                    fee_fraction=TRADING_FEE,
                    max_hops=MAX_HOPS,
                    max_paths=MAX_PATHS,
                    step=step,
                    state=state,
                    last_asset=last_asset,
                    strategy_mode=strategy_mode,
                    cfg=strategy_cfg,
                )

                if choice is None or used == "":
                    hold_count += 1
                    # Log HOLD decision
                    if step < 20:
                        debug_logs.append(f"Step {step+1}: HOLD (no profitable trade)")
                    continue

                amt = portfolio.get(used, 0)
                if amt <= 0:
                    break

                trade_count += 1
                # Debug logging for first 20 steps and every 100 steps
                if step < 20 or step % 100 == 0:
                    path_str = " → ".join(str(p) for p in choice.path)
                    ratio = choice.output_amount / amt if amt > 0 else 0
                    ev_ratio = choice.ev_gain_ratio
                    debug_logs.append(
                        f"Step {step+1}: TRADE {used}({amt:.2f}) → {path_str} → "
                        f"{choice.path[-1]}({choice.output_amount:.2f}), ratio={ratio:.4f}, "
                        f"EV_ratio={ev_ratio:.6f}"
                    )

                portfolio[used] = 0.0
                dest = choice.path[-1]
                last_asset = dest
                portfolio[dest] = portfolio.get(dest, 0) + choice.output_amount
                growth.append(sum(portfolio.values()))
            total = sum(portfolio.values())
            st.success("Simulation complete")
            st.metric("Final portfolio value", f"{total:.2f}")
            st.json({str(asset): amount for asset, amount in portfolio.items()})

            # Summary stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Trades executed", trade_count)
            with col2:
                st.metric("Steps held", hold_count)
            with col3:
                hold_pct = (hold_count / steps * 100) if steps > 0 else 0
                st.metric("Hold %", f"{hold_pct:.1f}%")

            if debug_logs:
                st.subheader("Debug Logs (First 20 steps + every 100 steps)")
                for log in debug_logs:
                    st.text(log)

            if len(growth) > 1:
                ret = (growth[-1] - growth[0]) / growth[0] if growth[0] else 0
                st.metric("Total return", f"{ret:.2%}")
                st.line_chart({"Portfolio value": growth})

elif mode == "Visualization":
    st.header("Graph Visualization")
    col1, col2 = st.columns(2)
    with col1:
        source = st.text_input("From asset", value="XRP", key="vis_source")
    with col2:
        target = st.text_input("To asset", value="USD", key="vis_target")
    if st.button("Visualize path"):
        with st.spinner("Building graph..."):
            graph = get_graph(use_mock=use_mock)
        if not graph:
            st.error("No order book data.")
        else:
            src = _resolve_asset(source)
            tgt = _resolve_asset(target)
            result = dijkstra_best_path(graph, src, tgt)
            if result is None:
                st.warning(f"No path from {source} to {target}.")
            else:
                dot = generate_graph_dot(graph, result.path)
                st.graphviz_chart(dot)
                st.success(f"Best path: {' → '.join(str(p) for p in result.path)}")
                sim = simulate_path(result.path, graph, 100.0, TRADING_FEE)
                st.metric("Simulated output (100 input)", f"{sim.output_amount:.4f}")

elif mode == "Comparison":
    st.header("Strategy Comparison")
    col1, col2 = st.columns(2)
    with col1:
        asset = st.text_input("Initial asset", value="XRP", key="comp_asset")
    with col2:
        amount = st.number_input(
            "Initial amount",
            min_value=0.01,
            value=1000.0,
            step=100.0,
            key="comp_amount",
        )
    steps = st.number_input(
        "Simulation steps", min_value=1, value=10, step=1, key="comp_steps"
    )
    strategy_mode = _strategy_selector("comp_")
    strategy_cfg = _build_strategy_cfg("comp_")
    target = st.text_input("Target asset for route", value="USD", key="comp_target")
    if st.button("Compare strategies"):
        with st.spinner("Running comparison..."):
            graph = get_graph(use_mock=use_mock)
        if not graph:
            st.error("No order book data.")
        else:
            a = _resolve_asset(asset)
            tgt = _resolve_asset(target)

            # Route strategy: single conversion to target
            route_result = dijkstra_best_path(graph, a, tgt)
            route_value = 0.0
            route_value_in_target = 0.0
            if route_result:
                sim = simulate_path(route_result.path, graph, amount, TRADING_FEE)
                route_value = sim.output_amount
                route_value_in_target = value_in_base(
                    tgt, route_value, tgt, graph, strategy_cfg
                )

            # Greedy strategy: simulate over steps
            portfolio = {a: amount}
            growth = [amount]
            state = AgentState()
            last_asset = None
            for step in range(steps - 1):
                choice, used = greedy_agent_step(
                    graph,
                    portfolio,
                    fee_fraction=TRADING_FEE,
                    max_hops=MAX_HOPS,
                    max_paths=MAX_PATHS,
                    step=step,
                    state=state,
                    last_asset=last_asset,
                    strategy_mode=strategy_mode,
                    cfg=strategy_cfg,
                )
                if choice is None or used == "":
                    break
                amt = portfolio.get(used, 0)
                if amt <= 0:
                    break
                portfolio[used] = 0.0
                dest = choice.path[-1]
                last_asset = dest
                portfolio[dest] = portfolio.get(dest, 0) + choice.output_amount
                growth.append(sum(portfolio.values()))
            greedy_value_in_target = 0.0
            for asset_k, asset_amt in portfolio.items():
                if asset_amt <= 0:
                    continue
                greedy_value_in_target += value_in_base(
                    asset_k, asset_amt, tgt, graph, strategy_cfg
                )

            st.subheader("Results")
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    f"Route value ({tgt})",
                    f"{route_value_in_target:.2f}" if route_result else "No path",
                )
            with col2:
                st.metric(f"Greedy value ({tgt})", f"{greedy_value_in_target:.2f}")
            if route_result and greedy_value_in_target > 0:
                diff = (
                    (
                        (greedy_value_in_target - route_value_in_target)
                        / route_value_in_target
                    )
                    * 100
                    if route_value_in_target
                    else 0
                )
                st.metric(f"Greedy vs Route ({tgt})", f"{diff:+.2f}%")
            if len(growth) > 1:
                st.line_chart({"Greedy portfolio": growth})

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Network:** Testnet/Devnet (see `XRPL_NETWORK` env). Mock ignores network."
)


if __name__ == "__main__":
    print("This is a Streamlit app. Run with: streamlit run app.py")
