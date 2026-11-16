"""Assemble a ScoreInput from real pipeline outputs (Group 4 graph/path + Group 5 sim + Group 3 price).

This module only reads and records provenance; it computes no score and substitutes no value.
"""

from __future__ import annotations

from sentinel.graph import attack
from sentinel.graph.builder import ANYONE
from sentinel.graph.model import EdgeType, Graph
from sentinel.graph.paths import Path
from sentinel.scoring.model import ScoreInput
from sentinel.sim.engine import SimResult


def from_pipeline(target: str, graph: Graph, path: Path, sim: SimResult | None,
                  eth_price=None, value_evidence: str | None = None) -> ScoreInput:
    path_nodes = set(path.nodes)
    depends_on = sum(1 for e in graph.edges.values()
                     if e.type == EdgeType.DEPENDS_ON and e.src in path_nodes)
    controlling = sum(1 for e in graph.edges.values()
                      if e.type == EdgeType.CONTROLS and e.dst in path_nodes)
    reachable = len(attack.attacker_paths(graph))
    total = len(attack.asset_sinks(graph))
    return ScoreInput(
        feasible=None if sim is None else sim.feasible,
        feasibility_evidence=None if sim is None else "simulation",
        profit_wei=None if sim is None else sim.attacker_profit_wei,
        eth_price_usd=eth_price,
        value_evidence=value_evidence,
        source_is_public=path.nodes[0] == ANYONE,
        path_len_edges=len(path.edges),
        reachable_assets=reachable,
        total_assets=total,
        depends_on_count=depends_on,
        controlling_authorities=controlling,
        target=target,
    )
