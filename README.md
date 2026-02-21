# XRPL Liquidity Routing & Opportunity Engine

A Python engine that connects to the XRP Ledger, fetches order books, builds a liquidity graph, finds optimal conversion routes, detects arbitrage opportunities, and simulates realistic execution (fees + slippage). It includes three agent strategies (`legacy`, `greedy`, `extended-greedy`). **It does not assume infinite liquidity.**

---

## Environment setup (all commands)

Use these commands from the project root to create a virtual environment, install dependencies, and verify the setup.

**Linux / macOS (bash/zsh):**

```bash
# 1. Go to project root
cd XRPL-Liquidity-Routing-AND-Opportunity-Engine

# 2. Create and activate a virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# 3. Upgrade pip
pip install --upgrade pip

# 4. Install dependencies
pip install -r requirements.txt

# 5. Verify (run tests)
python -m unittest discover -s xrpl_router/tests -v
```

**Windows (PowerShell):**

```powershell
# 1. Go to project root
cd XRPL-Liquidity-Routing-AND-Opportunity-Engine

# 2. Create and activate a virtual environment (optional but recommended)
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Upgrade pip
pip install --upgrade pip

# 4. Install dependencies
pip install -r requirements.txt

# 5. Verify (run tests)
python -m unittest discover -s xrpl_router/tests -v
```

**One-liner (if you already have the repo and want to install only):**

```bash
pip install -r requirements.txt
```

**Automated setup (Linux/macOS):** from project root run `./setup.sh` to create `.venv`, install deps, and run tests.

**Requirements:** Python 3.10+, `xrpl-py`, `networkx`, `pytest`, `streamlit` (see `requirements.txt`).

**Quick run commands after setup:**

| What | Command |
|------|--------|
| CLI (mock) | `python -m xrpl_router.cli route --from XRP --to USD --amount 100 --mock` |
| CLI (live) | `python -m xrpl_router.cli route --from XRP --to USD --amount 100` |
| Arbitrage | `python -m xrpl_router.cli arbitrage [--mock]` |
| Simulate | `python -m xrpl_router.cli simulate --asset XRP --amount 1000 --steps 5 --strategy greedy [--mock]` |
| Web UI | `streamlit run app.py` |
| Click-to-run (macOS) | Double-click `launch_app.command` |
| Tests | `python -m unittest discover -s xrpl_router/tests -v` |

---

## Features

- **Data layer**: XRPL Testnet/Devnet via `xrpl-py`, `book_offers`, normalized order book levels (rate, capacity).
- **Graph**: Directed multi-graph with capacity-limited edges; real-time rebuild.
- **Routing**: Dijkstra (best path by rate, weight = −log(rate)), Bellman-Ford (negative-cycle arbitrage).
- **Slippage simulation**: Level-by-level fill, configurable fees, effective rate and fill status.
- **Strategy modes**: `legacy` (EV-based), `greedy` (base-asset scoring + cooldown), `extended-greedy` (2-step lookahead MPC).
- **Opportunity evaluation**: Candidate routes, base-asset valuation, trade gating vs HOLD, cooldown/reversal block.
- **Arbitrage scanner**: Cycle detection + simulated fill and profit after fees.
- **Modes**: Route optimization (A), Arbitrage scan (B), Strategy simulation (C), and Strategy comparison in UI.

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

## Mock mode (no network)

Use **mock data** to run the full pipeline without connecting to XRPL (deterministic, for tests and UI).

- **CLI:** add `--mock` to any command.
- **UI:** check "Use mock data (no network)" in the sidebar.
- **Code:** `get_graph(use_mock=True)` in `xrpl_router.loader`.
- **Divergence demo:** in `app.py` and `xrpl_router/ui.py`, enable `Divergence demo market (mock only)` to use a crafted market where strategies diverge more clearly.

```bash
python -m xrpl_router.cli route --from XRP --to USD --amount 100 --mock
python -m xrpl_router.cli arbitrage --mock
python -m xrpl_router.cli simulate --asset XRP --amount 1000 --steps 5 --mock
```

Full-stack tests use the mock: `python -m unittest discover -s xrpl_router/tests -v`.

---

## Web UI

A Streamlit UI lets you run Route, Arbitrage, Simulate, and Comparison from the browser.

```bash
pip install -r requirements.txt   # includes streamlit
streamlit run app.py
```

Then open the URL shown (e.g. http://localhost:8501). Use the sidebar to switch modes and enable:
- **Use mock data (no network)**
- **Divergence demo market (mock only)** (for clearer strategy differences)

For macOS, you can launch the app by double-clicking `launch_app.command`.

---

## Installation

```bash
git clone <repo>
cd XRPL-Liquidity-Routing-AND-Opportunity-Engine
pip install -r requirements.txt
```

**Requirements:** Python 3.10+, `xrpl-py`, `networkx`, `streamlit` (for UI). No real transactions are sent (paper trading only).

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

### Mode C — Strategy simulation

**Input:** initial asset, amount, number of steps, strategy mode.

```bash
python -m xrpl_router.cli simulate --asset XRP --amount 1000 --steps 20 --strategy greedy
python -m xrpl_router.cli simulate --asset XRP --amount 1000 --steps 20 --strategy extended-greedy
python -m xrpl_router.cli simulate --asset XRP --amount 1000 --steps 20 --strategy legacy_greedy
```

**Output:** Final portfolio, final value, growth curve, total return.

Available strategy values:
- `legacy_greedy`: original EV-based strategy (comparison baseline)
- `greedy`: base-asset scoring + cooldown/reversal controls
- `extended-greedy`: two-step lookahead; executes first action then replans

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

| Parameter | Default | Description |
|---|---:|---|
| `XRPL_NETWORK` | `testnet` | `testnet` or `devnet` |
| `MAX_HOPS` / `MAX_PATHS` | `3` / `5` | Route candidate caps |
| `TRADING_FEE` | `0.001` | Per-hop fee fraction |
| `BOOK_DEPTH` | `20` | Order book depth |
| `STRATEGY_MODE` | `greedy` | `legacy_greedy` / `greedy` / `extended-greedy` |
| `BASE_ASSET` | `USD` | Fixed valuation asset |
| `MIN_BASE_GAIN_MULT` | `1.002` | Trade only above this base-value multiplier |
| `COOLDOWN_STEPS` | `2` | Cooldown window |
| `REVERSE_BLOCK` | `True` | Block immediate reversals during cooldown |
| `BASE_VALUE_MAX_HOPS` / `BASE_VALUE_MAX_PATHS` | `3` / `3` | Base valuation path caps |
| `LOOKAHEAD_DEPTH` | `2` | Extended-greedy planning depth |
| `LOOKAHEAD_TOPK` | `5` | First/second-step action expansion count |
| `LOOKAHEAD_MAX_HOPS` / `LOOKAHEAD_MAX_PATHS` | `3` / `5` | Lookahead route caps |

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
    strategy.py     # Legacy/Greedy/Extended-greedy policies
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
- **Greedy**: Scores actions by base-asset value improvement and applies HOLD/cooldown/reversal guards.
- **Extended-greedy**: Two-step lookahead (model predictive control): plan 2 steps, execute 1, replan next step.
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
