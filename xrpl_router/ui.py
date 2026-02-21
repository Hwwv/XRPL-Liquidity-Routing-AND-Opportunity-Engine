"""
Streamlit UI for XRPL Liquidity Routing & Opportunity Engine.
Run: streamlit run xrpl_router.ui
"""
import streamlit as st
from .config import DEFAULT_ISSUER, TRADING_FEE, MAX_HOPS, MAX_PATHS
from .loader import get_graph
from .routing import dijkstra_best_path
from .simulate import simulate_path
from .arbitrage import scan_arbitrage
from .strategy import greedy_agent_step


def _asset_key(currency: str, issuer: str | None) -> str:
    if currency.upper() == "XRP":
        return "XRP"
    return f"{currency.upper()}:{issuer or ''}"


def _resolve_asset(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "XRP"
    if s.upper() == "XRP":
        return "XRP"
    if ":" in s:
        cur, iss = s.split(":", 1)
        return _asset_key(cur, iss.strip() or None)
    return _asset_key(s, DEFAULT_ISSUER)


def main():
    st.set_page_config(page_title="XRPL Router", layout="wide")
    st.title("XRPL Liquidity Routing & Opportunity Engine")
    st.caption("Route optimization, arbitrage scan, and greedy agent simulation (paper trading only).")

    use_mock = st.sidebar.checkbox("Use mock data (no network)", value=True, help="Deterministic data for testing without XRPL.")
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

    else:
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

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Network:** Testnet/Devnet (see `XRPL_NETWORK` env). Mock ignores network.")


if __name__ == "__main__":
    main()
