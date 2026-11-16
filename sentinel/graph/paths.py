"""Shortest and k-shortest loopless paths.

`k_shortest_paths` is a real implementation of Yen's algorithm on top of Dijkstra: it returns up to
k distinct loopless paths in non-decreasing total weight, each a genuinely different route — not one
Dijkstra call returned k times. It is cross-checked against networkx.shortest_simple_paths in tests.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from sentinel.graph.model import Edge, Graph


@dataclass(frozen=True)
class Path:
    nodes: tuple[str, ...]
    edges: tuple[Edge, ...]
    cost: float

    def __len__(self) -> int:
        return len(self.edges)


def _dijkstra(graph: Graph, source: str, target: str,
              banned_edges: set[tuple[str, str, str]] = frozenset(),
              banned_nodes: set[str] = frozenset()) -> Path | None:
    if source in banned_nodes or source == target:
        if source == target:
            return Path((source,), (), 0.0)
        return None
    dist = {source: 0.0}
    prev: dict[str, Edge] = {}
    pq: list[tuple[float, str]] = [(0.0, source)]
    visited: set[str] = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u == target:
            break
        for e in graph.out_edges(u):
            if e.key in banned_edges or e.dst in banned_nodes:
                continue
            nd = d + e.weight
            if nd < dist.get(e.dst, float("inf")):
                dist[e.dst] = nd
                prev[e.dst] = e
                heapq.heappush(pq, (nd, e.dst))
    if target not in dist:
        return None
    edges: list[Edge] = []
    node = target
    while node != source:
        e = prev[node]
        edges.append(e)
        node = e.src
    edges.reverse()
    return Path(tuple([source] + [e.dst for e in edges]), tuple(edges), dist[target])


def shortest_path(graph: Graph, source: str, target: str) -> Path | None:
    return _dijkstra(graph, source, target)


def k_shortest_paths(graph: Graph, source: str, target: str, k: int) -> list[Path]:
    """Yen's algorithm: up to k loopless paths, non-decreasing cost."""
    if k <= 0 or source == target:
        return []
    first = _dijkstra(graph, source, target)
    if first is None:
        return []
    accepted: list[Path] = [first]
    candidates: list[tuple[float, int, Path]] = []
    counter = 0
    while len(accepted) < k:
        prev_path = accepted[-1]
        for i in range(len(prev_path.edges)):
            spur_node = prev_path.nodes[i]
            root_nodes = prev_path.nodes[: i + 1]
            root_edges = prev_path.edges[:i]
            root_cost = sum(e.weight for e in root_edges)

            banned_edges = set()
            for p in accepted:
                if len(p.nodes) > i and p.nodes[: i + 1] == root_nodes and i < len(p.edges):
                    banned_edges.add(p.edges[i].key)
            banned_nodes = set(root_nodes[:-1])

            spur = _dijkstra(graph, spur_node, target, banned_edges, banned_nodes)
            if spur is None:
                continue
            total_nodes = root_nodes[:-1] + spur.nodes
            total_edges = root_edges + spur.edges
            total_cost = root_cost + spur.cost
            candidate = Path(total_nodes, total_edges, total_cost)
            if candidate not in [c for _, _, c in candidates] and candidate not in accepted:
                counter += 1
                heapq.heappush(candidates, (total_cost, counter, candidate))
        if not candidates:
            break
        accepted.append(heapq.heappop(candidates)[2])
    return accepted
