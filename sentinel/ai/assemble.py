"""Assemble a NarrativeContext from real pipeline outputs, and compute the real evidence set."""

from __future__ import annotations

from sentinel.ai.narrative import NarrativeContext
from sentinel.graph.model import Graph
from sentinel.graph.paths import Path
from sentinel.scoring.model import ScoreResult
from sentinel.sim.engine import SimResult
from sentinel.static.slither_analyzer import AnalysisResult


def from_pipeline(target: str, analysis: AnalysisResult, graph: Graph, path: Path,
                  pattern: str | None, sim: SimResult | None = None,
                  score: ScoreResult | None = None) -> NarrativeContext:
    path_nodes = set(path.nodes)
    path_prov = [p for e in path.edges for p in e.provenance]
    on_path_labels = {graph.nodes[n].label.split("(")[0] for n in path.nodes}
    detector_facts = [
        {"name": d.name, "impact": d.slither_impact, "file": d.file, "lines": d.lines, "id": d.id}
        for d in analysis.detectors()
        if d.contract and d.function and f"{d.contract}.{d.function.split('(')[0]}" in on_path_labels
    ]
    sim_dict = None
    valid = set(path_prov) | {d["id"] for d in detector_facts}
    if sim is not None:
        txs = [s.tx_hash for s in sim.steps if s.tx_hash]
        sim_dict = {"feasible": sim.feasible, "profit_wei": sim.attacker_profit_wei, "tx_hashes": txs}
        valid |= set(txs)
    score_dict = None
    if score is not None:
        score_dict = score.to_dict()
        if score.status == "scored":
            valid |= {c.origin for c in score.components.values()}
    return NarrativeContext(
        target=target, pattern=pattern,
        path_labels=[graph.nodes[n].label for n in path.nodes],
        path_provenance=path_prov, detector_facts=detector_facts,
        sim=sim_dict, score=score_dict, valid_evidence=valid,
    )
