"""
Streamlit UI for XRPL Liquidity Routing & Opportunity Engine.
Run: streamlit run xrpl_router.ui
"""

from types import SimpleNamespace

import streamlit as st
from . import config as router_cfg
from .config import DEFAULT_ISSUER, TRADING_FEE, MAX_HOPS, MAX_PATHS
from .graph import Asset
from .loader import get_graph
from .routing import dijkstra_best_path
from .simulate import simulate_path
from .arbitrage import scan_arbitrage
from .strategy import (
    AgentState,
    STRATEGY_EXTENDED_GREEDY,
    STRATEGY_GREEDY,
    STRATEGY_LEGACY,
    greedy_agent_step,
    normalize_strategy_mode,
)


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


def main():
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
    mode = st.sidebar.radio("Mode", ["Route", "Arbitrage", "Simulate"], horizontal=True)

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

    else:
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
                state = AgentState()
                last_asset = None
                for t in range(steps - 1):
                    choice, used = greedy_agent_step(
                        graph,
                        portfolio,
                        fee_fraction=TRADING_FEE,
                        max_hops=MAX_HOPS,
                        max_paths=MAX_PATHS,
                        step=t,
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
                total = sum(portfolio.values())
                st.success("Simulation complete")
                st.metric("Final portfolio value", f"{total:.2f}")
                st.json({str(asset): amount for asset, amount in portfolio.items()})
                if len(growth) > 1:
                    ret = (growth[-1] - growth[0]) / growth[0] if growth[0] else 0
                    st.metric("Total return", f"{ret:.2%}")
                    st.line_chart({"Portfolio value": growth})

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Network:** Testnet/Devnet (see `XRPL_NETWORK` env). Mock ignores network."
    )


if __name__ == "__main__":
    main()
