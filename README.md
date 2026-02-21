# XRPL-Liquidity-Routing-AND-Opportunity-Engine

A Python-based engine for analyzing liquidity, routing trades, and detecting arbitrage opportunities on the XRP Ledger (XRPL).

This project builds a realistic simulation framework that:
	•	Connects to XRPL Testnet
	•	Fetches live order books
	•	Constructs a liquidity graph
	•	Finds optimal conversion routes
	•	Detects arbitrage cycles
	•	Simulates slippage and fees
	•	Evaluates trade opportunities using a greedy expected-value strategy

This is a research-style project combining:
	•	Graph algorithms (Dijkstra, Bellman-Ford)
	•	Liquidity modeling
	•	Capacity-constrained simulation
	•	Optimization under uncertainty

---

## Project Motivation

Liquidity routing on decentralized ledgers can be modeled as a graph problem:
	•	Nodes = currencies
	•	Edges = exchange offers
	•	Edge weights = exchange rates
	•	Capacities = order book depth

Finding the best trade route becomes a shortest-path problem.
Detecting arbitrage becomes a negative-cycle detection problem.
Realistic execution requires capacity-aware simulation.

This project aims to bridge theory and practical market behavior.

---

## Core Features

1. XRPL Data Integration
	•	Connects to XRPL Testnet via xrpl-py
	•	Fetches order books using book_offers
	•	Normalizes XRP and issued currency formats

---

2. Liquidity Graph Construction

Builds a directed multi-graph:
	•	Multiple edges per currency pair
	•	Each edge contains multiple price levels
	•	Each level has rate and capacity

---

3. Routing Engine

Simple Routing
	•	Uses best rate per pair
	•	Converts rates to weights using -log(rate)
	•	Runs Dijkstra to find optimal path

Arbitrage Detection
	•	Uses Bellman-Ford
	•	Detects negative-weight cycles
	•	Reports arbitrage opportunities

---

4. Slippage Simulation

Simulates real execution:
	•	Fills best order-book levels first
	•	Handles capacity exhaustion
	•	Applies configurable trading fees
	•	Returns effective output and execution status

---

5. Opportunity Evaluation Engine

Greedy strategy:
	1.	Generate candidate routes (max hop configurable)
	2.	Simulate execution
	3.	Estimate expected value
	4.	Select best route

No real transactions are executed (paper trading only).

---

## Project Structure

xrpl_router/\
│
├── config.py\
├── xrpl_client.py\
├── orderbooks.py\
├── graph.py\
├── routing.py\
├── arbitrage.py\
├── simulate.py\
├── strategy.py\
├── cli.py\
│
└── tests/


---

## Installation

git clone \
cd xrpl-router\
pip install -r requirements.txt

## Dependencies:
	•	Python 3.10+
	•	xrpl-py
	•	networkx (optional)
	•	numpy (optional)

---

## Usage

### Route Optimization

python -m xrpl_router.cli route \
  --from CAD \
  --to EUR \
  --amount 50

Output:

Best Path: CAD → XRP → EUR
Expected Output: 48.92 EUR
Effective Rate: 0.9784


---

### Arbitrage Scan

python -m xrpl_router.cli arbitrage

Output:

Arbitrage Cycle Detected:
CAD → XRP → EUR → CAD
Estimated Profit: 0.42%


---

### Greedy Agent Simulation

python -m xrpl_router.cli simulate \
  --asset USD \
  --amount 1000 \
  --steps 20

Output:

Final Portfolio Value: 1012.34 USD
Sharpe Ratio (simulated): 0.84


---

### Configuration

Edit config.py:

MAX_HOPS = 3
MAX_PATHS = 5
TRADING_FEE = 0.001
RISK_PENALTY = 0.002
BOOK_DEPTH = 20


---

## Algorithms Used

Routing:
	•	Dijkstra (O(E log V))

Arbitrage:
	•	Bellman-Ford (O(VE))

Simulation:
	•	Capacity-constrained level-by-level fill

Optional extensions:
	•	Min-cost flow
	•	k-shortest paths
	•	Contextual bandit strategy

---

## Design Principles
	•	Modular and testable
	•	Deterministic simulation mode
	•	No assumption of infinite liquidity
	•	Realistic execution modeling
	•	Clean separation between data, graph, routing, and strategy layers

---

## Limitations
	•	Uses XRPL Testnet only
	•	No real transaction submission
	•	No latency modeling
	•	No real-time streaming (future extension)
	•	No full multi-path flow optimization (future extension)

---

## Future Work
	•	Async streaming order book updates
	•	Multi-path splitting via min-cost flow
	•	Risk modeling using historical volatility
	•	Reinforcement learning strategy
	•	Performance benchmarking under large graphs

---

## Educational Value

This project demonstrates how:
	•	Financial markets map to graph theory
	•	Arbitrage becomes negative cycle detection
	•	Slippage introduces flow constraints
	•	Greedy strategies differ from global optimization

It is designed as both a research prototype and a learning tool.

---

## Disclaimer

This project is for educational and research purposes only.
It does not execute real trades and should not be considered financial advice.
