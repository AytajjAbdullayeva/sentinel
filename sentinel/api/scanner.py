"""Turn Solidity (a single paste or a whole repo of files) into a stored scan record: real static
analysis, attack graph, findings and grounded narratives. No chain here (feasibility/score need a sim).
Every number traces to a real fact, edge or Slither label."""

from __future__ import annotations

import re
import tempfile
from dataclasses import asdict
from pathlib import Path

from sentinel.ai import assemble as ai_assemble
from sentinel.ai.client import LLMClient, get_client
from sentinel.ai.narrative import generate
from sentinel.cli import scan as cli_scan
from sentinel.cli.main import _load_severity
from sentinel.graph import attack
from sentinel.graph.builder import build
from sentinel.graph.model import Graph
from sentinel.static.slither_analyzer import analyze


def _cytoscape(graph: Graph) -> dict:
    return {
        "nodes": [{"data": {"id": n.id, "label": n.label, "ntype": n.type.value}}
                  for n in graph.nodes.values()],
        "edges": [{"data": {"id": f"{e.src}->{e.dst}:{e.type.value}", "source": e.src, "target": e.dst,
                            "label": e.type.value, "provenance": list(e.provenance)}}
                  for e in graph.edges.values()],
    }


def _record(name: str, entry_rel: str, result, graph, impacts, sev_version, client) -> dict:
    findings = cli_scan.findings_from(result, graph, impacts)
    patterns = {h.where: h.pattern for h in attack.recognize(graph, result)}
    narratives = []
    for sink, paths in attack.attacker_paths(graph).items():
        path = paths[0]
        labels = [graph.nodes[n].label for n in path.nodes]
        pattern = next((p for w, p in patterns.items() if w in labels), None)
        ctx = ai_assemble.from_pipeline(name, result, graph, path, pattern, sim=None, score=None)
        narratives.append(generate(ctx, client).to_dict())
    contracts = len({fct.contract for fct in result.structure() if fct.contract})
    return {
        "name": name, "entry": entry_rel, "compiler": result.solc_version, "contracts": contracts,
        "facts": len(result.facts), "max_severity": max((f.severity_score for f in findings), default=0.0),
        "severity_config": sev_version, "findings": [asdict(f) for f in findings],
        "graph": _cytoscape(graph), "narratives": narratives,
    }


def scan_files(files: dict[str, str], entry: str, name: str, client: LLMClient | None = None) -> dict:
    """Analyze `entry` (a path within `files`) with every repo file present so imports resolve."""
    client = client or get_client()
    impacts, _default, sev_version = _load_severity()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for path, content in files.items():
            dst = root / path
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content)
        result = analyze(root / entry, root=root)
        graph = build(result)
        return _record(name, entry, result, graph, impacts, sev_version, client)


def scan_source_text(name: str, source: str, client: LLMClient | None = None) -> dict:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", name) or "input"
    return scan_files({f"{safe}.sol": source}, f"{safe}.sol", name, client)
