from xrpl_router.loader import get_graph
from xrpl_router.strategy import greedy_agent_step
from xrpl_router.config import TRADING_FEE, MAX_HOPS, MAX_PATHS

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

from xrpl_router.graph import Asset

graph = get_graph(use_mock=True)
asset = _resolve_asset('XRP')
amount = 1000.0
portfolio = {asset: amount}
print(f'Initial: { {str(k): v for k, v in portfolio.items()} }')

for step in range(20):
    choice, used = greedy_agent_step(graph, portfolio, fee_fraction=TRADING_FEE, max_hops=MAX_HOPS, max_paths=MAX_PATHS)
    if choice is None or used == "" or choice.expected_value <= 0:
        print(f'Step {step+1}: No trade')
        break
    amt = portfolio.get(used, 0)
    if amt <= 0:
        print(f'Step {step+1}: No amount')
        break
    path_str = " → ".join(str(p) for p in choice.path)
    ratio = choice.output_amount / amt if amt > 0 else 0
    print(f'Step {step+1}: {used}({amt:.2f}) → {path_str} → {choice.path[-1]}({choice.output_amount:.2f}), ratio={ratio:.4f}')
    
    portfolio[used] = 0.0
    dest = choice.path[-1]
    portfolio[dest] = portfolio.get(dest, 0) + choice.output_amount
    total = sum(portfolio.values())
    print(f'Portfolio: { {str(k): v for k, v in portfolio.items()} }, total={total:.2f}')
    if total < 0.1:
        break