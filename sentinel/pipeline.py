"""End-to-end pipeline that composes the verified stages into one call.

Static path (no chain): ingest (solc) -> static facts (Slither) -> attack graph -> grounded narrative,
score = insufficient_data (feasibility needs simulation). Full path (with a deployment + exploit
strategy): also runs the real Anvil simulation, the sourced score, and a simulation-grounded narrative.
Nothing here invents data; it only wires together Groups 1-10.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from web3 import Web3

from sentinel.ai import assemble as ai_assemble
from sentinel.ai.client import LLMClient, get_client
from sentinel.ai.narrative import Narrative, generate
from sentinel.graph import attack
from sentinel.graph.builder import ANYONE, DeployedContext, build
from sentinel.graph.model import Graph
from sentinel.graph.paths import Path as GPath, shortest_path
from sentinel.scoring import assemble as score_assemble, config as scfg
from sentinel.scoring.engine import score
from sentinel.scoring.model import ScoreResult
from sentinel.sim.engine import SimResult, run as sim_run
from sentinel.static.slither_analyzer import analyze


@dataclass
class ProtocolAnalysis:
    name: str
    compiler: str
    contracts: int
    facts: int
    graph_nodes: int
    graph_edges: int
    attacker_reachable_sinks: int
    patterns: list[str]
    score: ScoreResult | None = None
    narrative: Narrative | None = None
    graph: Graph = None

    def summary(self) -> str:
        s = self.score.display if self.score else "n/a (static only)"
        return (f"{self.name:<26} solc {self.compiler:<7} contracts={self.contracts} facts={self.facts} "
                f"graph={self.graph_nodes}n/{self.graph_edges}e paths={self.attacker_reachable_sinks} "
                f"patterns={self.patterns or '-'} score={s}")


def _first_eth_path(graph: Graph) -> GPath | None:
    for sink in attack.asset_sinks(graph):
        if graph.nodes[sink].label == "ETH" and (p := shortest_path(graph, ANYONE, sink)):
            return p
    return None


def analyze_static(name: str, sol_files: list[Path], client: LLMClient | None = None) -> ProtocolAnalysis:
    client = client or get_client()
    result = analyze(sol_files[0], root=sol_files[0].parent)
    graph = build(result)
    patterns = sorted({h.pattern for h in attack.recognize(graph, result)})
    contracts = len({f.contract for f in result.structure() if f.contract})
    pa = ProtocolAnalysis(name, result.solc_version, contracts, len(result.facts),
                          len(graph.nodes), len(graph.edges), len(attack.attacker_paths(graph)),
                          patterns, graph=graph)
    path = _first_eth_path(graph)
    if path is not None:
        pattern = patterns[0] if patterns else None
        ctx = ai_assemble.from_pipeline(name, result, graph, path, pattern, sim=None, score=None)
        pa.narrative = generate(ctx, client)
    return pa


def analyze_full(name: str, w3: Web3, analysis, ctx: DeployedContext, attacker_addresses, steps,
                 eth_price, client: LLMClient | None = None) -> ProtocolAnalysis:
    """Full path for a deployed protocol with a concrete exploit strategy (Groups 4-6, 10)."""
    client = client or get_client()
    graph = build(analysis, ctx)
    patterns = sorted({h.pattern for h in attack.recognize(graph, analysis)})
    contracts = len({f.contract for f in analysis.structure() if f.contract})
    path = _first_eth_path(graph)
    sim: SimResult = sim_run(w3, attacker_addresses, steps)
    cfg = scfg.load()
    sc = score(score_assemble.from_pipeline(name, graph, path, sim, eth_price, "declared"), cfg)
    ctx_ai = ai_assemble.from_pipeline(name, analysis, graph, path, patterns[0] if patterns else None, sim, sc)
    return ProtocolAnalysis(name, analysis.solc_version, contracts, len(analysis.facts),
                            len(graph.nodes), len(graph.edges), len(attack.attacker_paths(graph)),
                            patterns, score=sc, narrative=generate(ctx_ai, client), graph=graph)
