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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress Streamlit warnings when run in bare mode
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message=".*Session state does not function.*")
warnings.filterwarnings("ignore", message=".*to view this Streamlit app on a browser.*")

# Suppress Streamlit logging warnings
logging.getLogger("streamlit").setLevel(logging.ERROR)

from xrpl_router.config import DEFAULT_ISSUER, TRADING_FEE, MAX_HOPS, MAX_PATHS
from xrpl_router.graph import Asset
from xrpl_router.loader import get_graph
from xrpl_router.routing import dijkstra_best_path
from xrpl_router.simulate import simulate_path
from xrpl_router.arbitrage import scan_arbitrage
from xrpl_router.strategy import greedy_agent_step

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
            path_edges.add((path[i], path[i+1]))
    
    for from_asset, edges in graph.items():
        for edge in edges:
            to_asset = edge.dst
            rate = edge.best_rate()
            if rate is not None:
                label = f"{rate:.4f} (fee:{TRADING_FEE:.4f})"
                color = "red" if (from_asset, to_asset) in path_edges else "black"
                penwidth = "3" if (from_asset, to_asset) in path_edges else "1"
                dot_lines.append(f'  "{from_asset}" -> "{to_asset}" [label="{label}", color={color}, penwidth={penwidth}];')
    
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


# --- Streamlit app (single entrypoint so context is correct) ---
st.set_page_config(page_title="XRPL Router", layout="wide")
st.title("XRPL Liquidity Routing & Opportunity Engine")
st.caption("Route optimization, arbitrage scan, and greedy agent simulation (paper trading only).")

use_mock = st.sidebar.checkbox("Use mock data (no network)", value=True, help="Deterministic data for testing without XRPL.")
mode = st.sidebar.radio("Mode", ["Route", "Arbitrage", "Simulate", "Visualization", "Comparison"], horizontal=True)

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
            st.error("No order book data. Try live data (uncheck mock) or check network.")
        else:
            src = _resolve_asset(source)
            tgt = _resolve_asset(target)
            result = dijkstra_best_path(graph, src, tgt)
            if result is None:
                st.warning(f"No path from {source} to {target}.")
            else:
                sim = simulate_path(result.path, graph, amount, TRADING_FEE)
                st.success("Best path: **" + " → ".join(str(p) for p in result.path) + "**")
                st.metric("Expected output (no slippage)", f"{result.effective_rate * amount:.4f}")
                st.metric("Simulated output (slippage + fees)", f"{sim.output_amount:.4f}")
                st.metric("Effective rate", f"{sim.effective_rate:.4f}")

elif mode == "Arbitrage":
    st.header("Arbitrage scan")
    trial_amount = st.number_input("Trial amount", min_value=1.0, value=1000.0, step=100.0)
    if st.button("Scan for arbitrage"):
        with st.spinner("Building graph and running Bellman-Ford..."):
            graph = get_graph(use_mock=use_mock)
        if not graph:
            st.error("No order book data.")
        else:
            report = scan_arbitrage(graph, trial_amount=trial_amount, fee_fraction=TRADING_FEE)
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
        amount = st.number_input("Initial amount", min_value=0.01, value=1000.0, step=100.0)
    with col3:
        steps = st.number_input("Steps", min_value=1, value=20, step=1)
    if st.button("Run simulation"):
        with st.spinner("Running greedy agent..."):
            graph = get_graph(use_mock=use_mock)
        if not graph:
            st.error("No order book data.")
        else:
            a = _resolve_asset(asset)
            portfolio = {a: amount}
            growth = [amount]
            for _ in range(steps - 1):
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
                growth.append(sum(portfolio.values()))
            total = sum(portfolio.values())
            st.success("Simulation complete")
            st.metric("Final portfolio value", f"{total:.2f}")
            st.json({str(asset): amount for asset, amount in portfolio.items()})
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
        amount = st.number_input("Initial amount", min_value=0.01, value=1000.0, step=100.0, key="comp_amount")
    steps = st.number_input("Simulation steps", min_value=1, value=10, step=1, key="comp_steps")
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
            route_value = 0
            if route_result:
                sim = simulate_path(route_result.path, graph, amount, TRADING_FEE)
                route_value = sim.output_amount
            
            # Greedy strategy: simulate over steps
            portfolio = {a: amount}
            growth = [amount]
            for _ in range(steps - 1):
                choice, used = greedy_agent_step(graph, portfolio, fee_fraction=TRADING_FEE, max_hops=MAX_HOPS, max_paths=MAX_PATHS)
                if choice is None or used == "" or choice.expected_value <= 0:
                    break
                amt = portfolio.get(used, 0)
                if amt <= 0:
                    break
                portfolio[used] = 0.0
                dest = choice.path[-1]
                portfolio[dest] = portfolio.get(dest, 0) + choice.output_amount
                growth.append(sum(portfolio.values()))
            greedy_value = sum(portfolio.values())
            
            st.subheader("Results")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Route to target", f"{route_value:.2f}" if route_result else "No path")
            with col2:
                st.metric("Greedy simulation", f"{greedy_value:.2f}")
            if route_result and greedy_value > 0:
                diff = ((greedy_value - route_value) / route_value) * 100 if route_value else 0
                st.metric("Greedy vs Route", f"{diff:+.2f}%")
            if len(growth) > 1:
                st.line_chart({"Greedy portfolio": growth})

st.sidebar.markdown("---")
st.sidebar.markdown("**Network:** Testnet/Devnet (see `XRPL_NETWORK` env). Mock ignores network.")


if __name__ == "__main__":
    print("This is a Streamlit app. Run with: streamlit run app.py")
