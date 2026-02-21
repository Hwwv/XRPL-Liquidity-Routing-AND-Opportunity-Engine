from xrpl_router.loader import get_graph
from xrpl_router.strategy import AgentState, greedy_agent_step
from xrpl_router.config import TRADING_FEE, MAX_HOPS, MAX_PATHS
from xrpl_router.graph import Asset


def _resolve_asset(s: str):
    from xrpl_router.config import DEFAULT_ISSUER

    s = (s or "").strip()
    if not s:
        return Asset("XRP", None)
    if s.upper() == "XRP":
        return Asset("XRP", None)
    if ":" in s:
        cur, iss = s.split(":", 1)
        return Asset(cur.upper(), iss.strip() or None)
    return Asset(s.upper(), DEFAULT_ISSUER)


graph = get_graph(use_mock=True)
asset = _resolve_asset("XRP")
amount = 1000.0
portfolio = {asset: amount}
print(f"Initial: { {str(k): v for k, v in portfolio.items()} }")
state = AgentState()

trades = []
holds = []

for step in range(1000):
    choice, used = greedy_agent_step(
        graph,
        portfolio,
        fee_fraction=TRADING_FEE,
        max_hops=MAX_HOPS,
        max_paths=MAX_PATHS,
        step=step,
        state=state,
    )
    if choice is None or used == "":
        holds.append(step)
        if step < 5 or step % 100 == 0:
            print(f"Step {step+1}: HOLD")
        continue

    trades.append(step)
    amt = portfolio.get(used, 0)
    if amt <= 0:
        break
    path_str = " → ".join(str(p) for p in choice.path)
    ratio = choice.output_amount / amt if amt > 0 else 0

    if step < 5 or step % 100 == 0:
        print(
            f"Step {step+1}: TRADE {used}({amt:.2f}) → {path_str}, output={choice.output_amount:.2f}"
        )

    portfolio[used] = 0.0
    dest = choice.path[-1]
    portfolio[dest] = portfolio.get(dest, 0) + choice.output_amount
    total = sum(portfolio.values())

    if step < 5 or step % 100 == 0:
        print(
            f"  Portfolio: { {str(k): round(v, 2) for k, v in portfolio.items() if v > 0} }, total={total:.2f}"
        )

    if total < 0.1:
        print(f"Portfolio collapsed at step {step+1}")
        break

final_total = sum(portfolio.values())
print(f"\n=== FINAL STATS ===")
print(f"Total steps: {len(trades) + len(holds)}")
print(f"Trades: {len(trades)} ({len(trades)/(len(trades)+len(holds))*100:.1f}%)")
print(f"Holds: {len(holds)} ({len(holds)/(len(trades)+len(holds))*100:.1f}%)")
print(
    f"Final portfolio: { {str(k): round(v, 2) for k, v in portfolio.items() if v > 0} }"
)
print(f"Final total value: {final_total:.2f} (started with 1000.0)")
print(f"Return: {(final_total - 1000.0)/1000.0*100:.2f}%")
