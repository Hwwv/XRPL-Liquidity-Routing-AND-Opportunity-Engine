"""
Routing engine: Dijkstra (best path by rate) and Bellman-Ford (negative cycle = arbitrage).
Weights: -log(rate) so that shortest path = best product of rates.
"""
import math
import heapq
from typing import NamedTuple

from .graph import MarketEdge


class PathResult(NamedTuple):
    """Best path and effective rate (product of rates), no slippage."""
    path: list[str]
    effective_rate: float
    weight: float  # sum of -log(rate)


def _weight(rate: float) -> float:
    """Edge weight for minimization: -log(rate). Smaller weight = better rate."""
    if rate <= 0:
        return float("inf")
    return -math.log(rate)


def _get_nodes_and_edges(graph: dict[str, list[MarketEdge]]):
    """Return set of nodes and list of (u, v, rate, weight)."""
    nodes = set(graph.keys())
    edges: list[tuple[str, str, float, float]] = []
    for u, edge_list in graph.items():
        for e in edge_list:
            nodes.add(e.dst)
            r = e.best_rate()
            if r is not None and r > 0:
                w = _weight(r)
                edges.append((u, e.dst, r, w))
    return nodes, edges


def dijkstra_best_path(
    graph: dict[str, list[MarketEdge]],
    source: str,
    target: str,
) -> PathResult | None:
    """
    Best path from source to target using top-of-book rate per edge.
    Weight = -log(rate). O(E log V) with heap.
    Returns path, effective_rate (product of rates), and total weight; or None if no path.
    """
    nodes, edges = _get_nodes_and_edges(graph)
    if source not in nodes or target not in nodes:
        return None

    # Build adjacency: from u -> [(v, weight, rate), ...]
    adj: dict[str, list[tuple[str, float, float]]] = {n: [] for n in nodes}
    for u, v, rate, w in edges:
        adj[u].append((v, w, rate))

    dist: dict[str, float] = {n: float("inf") for n in nodes}
    dist[source] = 0.0
    parent: dict[str, tuple[str, float]] = {}  # node -> (prev_node, rate)
    heap: list[tuple[float, str]] = [(0.0, source)]

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        if u == target:
            break
        for v, w, rate in adj[u]:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                parent[v] = (u, rate)
                heapq.heappush(heap, (dist[v], v))

    if target not in parent and source != target:
        return None
    if source == target:
        return PathResult(path=[source], effective_rate=1.0, weight=0.0)

    path: list[str] = []
    rate_product = 1.0
    cur = target
    while cur != source:
        path.append(cur)
        prev, rate = parent[cur]
        rate_product *= rate
        cur = prev
    path.append(source)
    path.reverse()
    return PathResult(path=path, effective_rate=rate_product, weight=dist[target])


def bellman_ford_negative_cycle(
    graph: dict[str, list[MarketEdge]],
) -> list[str] | None:
    """
    Detect negative cycle in graph with weights -log(rate).
    O(VE). Returns one cycle (list of nodes) if found, else None.
    """
    nodes, edges = _get_nodes_and_edges(graph)
    nodes_list = list(nodes)
    n = len(nodes_list)
    node_to_id = {node: i for i, node in enumerate(nodes_list)}
    id_to_node = nodes_list

    # Bellman-Ford: relax V-1 times, then one more to detect cycle
    INF = float("inf")
    dist = [INF] * n
    pred: list[int | None] = [None] * n
    # Start from first node (arbitrary; we want any negative cycle)
    dist[0] = 0.0

    for _ in range(n - 1):
        for u, v, _rate, w in edges:
            i, j = node_to_id.get(u), node_to_id.get(v)
            if i is None or j is None:
                continue
            if dist[i] != INF and dist[i] + w < dist[j]:
                dist[j] = dist[i] + w
                pred[j] = i

    # One more pass: if we can relax, we're in a negative cycle
    cycle_node_id: int | None = None
    for u, v, _rate, w in edges:
        i, j = node_to_id.get(u), node_to_id.get(v)
        if i is None or j is None:
            continue
        if dist[i] != INF and dist[i] + w < dist[j]:
            cycle_node_id = j
            break

    if cycle_node_id is None:
        return None

    # Find a node in the cycle by walking back n steps
    in_cycle = cycle_node_id
    for _ in range(n):
        if pred[in_cycle] is not None:
            in_cycle = pred[in_cycle]

    # Reconstruct cycle: follow pred from in_cycle until we return to in_cycle
    cycle_ids: list[int] = [in_cycle]
    cur = pred[in_cycle]
    while cur is not None and cur != in_cycle and len(cycle_ids) <= n:
        cycle_ids.append(cur)
        cur = pred[cur]
    if cur == in_cycle:
        cycle_ids.append(in_cycle)
    cycle_ids.reverse()
    return [id_to_node[i] for i in cycle_ids]
