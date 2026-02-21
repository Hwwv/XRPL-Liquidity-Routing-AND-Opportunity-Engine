# XRPL Liquidity Routing & Opportunity Engine

A Python engine that connects to the XRP Ledger, fetches order books, builds a liquidity graph, finds optimal conversion routes, detects arbitrage opportunities, and simulates realistic execution (fees + slippage) with a greedy expected-value strategy. **It does not assume infinite liquidity.**

---

## Features

- **Data layer**: XRPL Testnet/Devnet via `xrpl-py`, `book_offers`, normalized order book levels (rate, capacity).
- **Graph**: Directed multi-graph with capacity-limited edges; real-time rebuild.
- **Routing**: Dijkstra (best path by rate, weight = −log(rate)), Bellman-Ford (negative-cycle arbitrage).
- **Slippage simulation**: Level-by-level fill, configurable fees, effective rate and fill status.
- **Opportunity evaluation**: Candidate routes (max hops, k-shortest), expected value, greedy best route.
- **Arbitrage scanner**: Cycle detection + simulated fill and profit after fees.
- **Modes**: Route optimization (A), Arbitrage scan (B), Greedy agent simulation (C).

---

## Developer environments: Testnet and Devnet

The engine supports two XRPL developer networks via the **`XRPL_NETWORK`** environment variable:

| Environment | `XRPL_NETWORK` | JSON-RPC endpoint |
|-------------|----------------|--------------------|
| **Testnet** | `testnet` (default) | `https://s.altnet.rippletest.net:51234` |
| **Devnet**  | `devnet`            | `https://s.devnet.rippletest.net:51234` |

- **Testnet**: Public test network; use for integration with testnet faucets and gateways.
- **Devnet**: Separate development network; use for isolated testing.

**Examples:**

```bash
# Use Testnet (default)
python -m xrpl_router.cli route --from XRP --to USD --amount 100

# Use Devnet
export XRPL_NETWORK=devnet
python -m xrpl_router.cli route --from XRP --to USD --amount 100
```

Optional: `LOG_LEVEL=DEBUG` for verbose logs.

---

## Installation

```bash
git clone <repo>
cd XRPL-Liquidity-Routing-AND-Opportunity-Engine
pip install -r requirements.txt
```

**Requirements:** Python 3.10+, `xrpl-py`, `networkx` (optional). No real transactions are sent (paper trading only).

---

## Usage

### Mode A — Route optimization

**Input:** source asset, target asset, amount.

```bash
python -m xrpl_router.cli route --from XRP --to USD --amount 100
```

**Output:** Best path, expected output (no slippage), simulated output (with slippage/fees), effective rate.

Example:

```
Best Path: XRP → USD:rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B
Expected Output (no slippage): 98.50
Simulated Output (with slippage/fees): 97.12
Effective Rate: 0.9712
```

---

### Mode B — Arbitrage scan

**Input:** (optional) trial amount for profit estimate.

```bash
python -m xrpl_router.cli arbitrage
# or
python -m xrpl_router.cli arbitrage --trial-amount 1000
```

**Output:** Whether a negative cycle was found; if yes: cycle path, estimated profit %, absolute profit, confidence.

Example:

```
Arbitrage Cycle Detected:
   XRP → USD:... → EUR:... → XRP
   Estimated Profit: 0.42%
   Profit (absolute): 4.20
   Confidence: 0.95
```

---

### Mode C — Greedy agent simulation

**Input:** initial asset, amount, number of steps.

```bash
python -m xrpl_router.cli simulate --asset XRP --amount 1000 --steps 20
```

**Output:** Final portfolio, final value, growth curve (value per step), total return.

Example:

```
Final Portfolio: {'XRP': 0, 'USD:rvY...': 1012.34}
Final Portfolio Value: 1012.34
Growth Curve (value per step): [1000, 1002.1, ...]
Total Return: 1.23%
```

---

## Configuration

Edit `xrpl_router/config.py` or set environment variables:

| Parameter        | Default | Description                    |
|------------------|--------|--------------------------------|
| `XRPL_NETWORK`   | testnet| `testnet` or `devnet`          |
| `MAX_HOPS`       | 3      | Max path length for routing   |
| `MAX_PATHS`      | 5      | Max candidate paths            |
| `TRADING_FEE`    | 0.001  | Per-hop fee fraction (0.1%)   |
| `RISK_PENALTY`   | 0.002  | Execution uncertainty penalty |
| `BOOK_DEPTH`     | 20     | Order book depth (levels)     |

---

## Project structure

```
xrpl_router/
    config.py       # Network (Testnet/Devnet), fees, hop limit
    xrpl_client.py  # JSON-RPC client, book_offers
    orderbooks.py   # Fetch books, normalize to Level (rate, capacity)
    graph.py        # Directed multi-graph, MarketEdge
    routing.py      # Dijkstra, Bellman-Ford
    arbitrage.py    # Negative-cycle scan, profit estimate
    simulate.py     # Slippage + fee simulation
    strategy.py     # Candidate paths, expected value, greedy choice
    cli.py          # Modes A, B, C
    tests/
```

---

## Algorithms and complexity

| Component      | Algorithm / idea              | Target complexity |
|----------------|-------------------------------|-------------------|
| Best path      | Dijkstra, weight = −log(rate) | O(E log V)        |
| Arbitrage      | Bellman-Ford, negative cycle  | O(VE)             |
| Simulation     | Capacity-constrained fill     | O(K × H × L)      |

With V = currencies, E = edges, L = levels per edge, K = candidate paths, H = hops. Designed to be efficient for V ≤ 20, E ≤ 200, L ≤ 20.

---

## Performance and realism

- **No infinite liquidity**: Execution is simulated by filling levels in order until capacity or amount is exhausted.
- **Fees and slippage**: Per-hop fee and level-by-level fill produce realistic effective rates and fill status.
- **Expected value**: Uses P(success) × output − cost with optional risk penalty; avoids assuming infinite profit.
- **Deterministic tests**: `xrpl_router/tests` use synthetic graphs (no live XRPL) for unit tests.

---

## Running tests

```bash
python -m unittest discover -s xrpl_router/tests -v
```

---

## Example run logs (conceptual)

**Route (Testnet):**

```
$ XRPL_NETWORK=testnet python -m xrpl_router.cli route --from XRP --to USD --amount 50
INFO xrpl_router.xrpl_client: Using XRPL endpoint: https://s.altnet.rippletest.net:51234
Best Path: XRP → USD:rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B
Expected Output (no slippage): 49.25
Simulated Output (with slippage/fees): 48.52
Effective Rate: 0.9704
```

**Arbitrage (no cycle):**

```
$ python -m xrpl_router.cli arbitrage
No arbitrage cycle detected.
```

**Simulate (2 steps):**

```
$ python -m xrpl_router.cli simulate --asset XRP --amount 100 --steps 2
Final Portfolio: {'XRP': 0.0, 'USD:rvY...': 99.8}
Final Portfolio Value: 99.80
Total Return: -0.20%
```

---

## Limitations

- Testnet/Devnet only; no mainnet.
- Paper trading only; no transaction submission.
- No latency or real-time streaming (possible future extension).
- Default order book pairs are set in `config.py` (edit for other gateways/pairs).

---

## Disclaimer

For educational and research purposes only. No real trades; not financial advice.
