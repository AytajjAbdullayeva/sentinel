"""Queries over the attack graph, and evidence-based recognition of known exploit topologies.

Nothing here decides feasibility (that is Group 5, real EVM execution). These functions only report
graph topology and the facts behind it: which asset sinks an attacker (or an authority) can reach,
and whether the shape matches a documented pattern.
"""

from __future__ import annotations

from dataclasses import dataclass

from sentinel.graph.builder import ANYONE
from sentinel.graph.model import EdgeType, Graph, NodeType
from sentinel.graph.paths import Path, k_shortest_paths
from sentinel.static.slither_analyzer import AnalysisResult


def asset_sinks(graph: Graph) -> list[str]:
    return [n.id for n in graph.nodes_of(NodeType.ASSET)]


def attacker_paths(graph: Graph, k: int = 3) -> dict[str, list[Path]]:
    return {sink: paths for sink in asset_sinks(graph)
            if (paths := k_shortest_paths(graph, ANYONE, sink, k))}


def authority_paths(graph: Graph, k: int = 3) -> dict[tuple[str, str], list[Path]]:
    out = {}
    for auth in graph.nodes_of(NodeType.AUTHORITY):
        for sink in asset_sinks(graph):
            if paths := k_shortest_paths(graph, auth.id, sink, k):
                out[(auth.id, sink)] = paths
    return out


@dataclass
class PatternHit:
    pattern: str
    where: str
    evidence: list[str]
    path: Path | None = None


def recognize(graph: Graph, result: AnalysisResult) -> list[PatternHit]:
    return [*_reentrancy(graph, result), *_oracle_manipulation(graph, result), *_governance_takeover(graph)]


def _reentrancy(graph: Graph, result: AnalysisResult) -> list[PatternHit]:
    """Reentrancy: an anyone-reachable function that transfers value AND carries a Slither
    reentrancy detector fact (external call before state write)."""
    # Detector facts name functions without a signature ("withdraw"); structure facts include it
    # ("withdraw()"). Match on (contract, bare name).
    def bare(name: str) -> str:
        return name.split("(", 1)[0]

    reentrancy_facts = {(f.contract, bare(f.function or "")): f
                        for f in result.detectors() if f.name.startswith("reentrancy")}
    hits = []
    for sink, paths in attacker_paths(graph).items():
        for path in paths:
            transfer = next((e for e in path.edges if e.type == EdgeType.TRANSFERS), None)
            if not transfer:
                continue
            fn_node = graph.nodes[transfer.src]
            contract, fn = fn_node.label.split(".", 1)
            det = reentrancy_facts.get((contract, bare(fn)))
            if det:
                hits.append(PatternHit(
                    "reentrancy", fn_node.label,
                    [f"slither:{det.name}@{det.file}:{det.lines}", f"transfer-edge:{transfer.provenance}",
                     f"reachable-by:anyone via {' -> '.join(path.nodes)}"],
                    path))
    return hits


def _oracle_manipulation(graph: Graph, result: AnalysisResult) -> list[PatternHit]:
    """Oracle manipulation: one function DEPENDS_ON a price source and can move value, while an
    anyone-reachable path can influence that same source's inputs (a second entry on the dependency)."""
    hits = []
    dep_edges = [e for e in graph.edges.values() if e.type == EdgeType.DEPENDS_ON]
    for dep in dep_edges:
        borrower = dep.src
        # does the borrower also (transitively) reach an asset sink from anyone?
        reaches_value = any(borrower in p.nodes
                            for paths in attacker_paths(graph).values() for p in paths)
        if reaches_value:
            hits.append(PatternHit(
                "oracle_manipulation", graph.nodes[borrower].label,
                [f"depends-on:{graph.nodes[dep.dst].label} via {dep.provenance}",
                 "borrower-reachable-by-anyone-and-moves-value"]))
    return hits


def _governance_takeover(graph: Graph) -> list[PatternHit]:
    """Governance takeover: an AUTHORITY controls a function that can move value to an asset sink."""
    hits = []
    for (auth, sink), paths in authority_paths(graph).items():
        for path in paths:
            if any(e.type == EdgeType.CONTROLS for e in path.edges) and \
               any(e.type == EdgeType.TRANSFERS for e in path.edges):
                hits.append(PatternHit(
                    "governance_takeover", graph.nodes[auth].label,
                    [f"controls-then-transfers to {graph.nodes[sink].label}",
                     f"path: {' -> '.join(path.nodes)}"],
                    path))
                break
    return hits
