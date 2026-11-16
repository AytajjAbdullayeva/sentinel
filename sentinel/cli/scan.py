"""Static scan: compile + Slither + attack graph -> findings identified by contract.function, not a DB id.

A finding's stable id is a hash of the contract-and-signature node labels along the attack path plus
the pattern. It does not contain any deployment address, run id or database key, so it is identical
across runs of the same source — which is what lets the CI gate diff two versions meaningfully.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sentinel.graph import attack
from sentinel.graph.builder import build
from sentinel.graph.model import EdgeType
from sentinel.static.slither_analyzer import analyze

_IMPACT_ORDER = {"High": 4, "Medium": 3, "Low": 2, "Informational": 1}


@dataclass
class Finding:
    stable_id: str
    entry: str                 # "Vault.withdraw()"
    sink: str
    pattern: str | None
    max_impact: str            # Slither's own impact label, or "None"
    severity_score: float
    evidence: list[str] = field(default_factory=list)
    path: list[str] = field(default_factory=list)


def _bare(name: str) -> str:
    return name.split("(", 1)[0]


def _stable_id(path_labels: list[str]) -> str:
    # Identity is the structural route (contract.signature nodes + sink), never the pattern/severity,
    # so the SAME path keeps its id across a code change and the gate can see its severity move.
    return hashlib.sha256("->".join(path_labels).encode()).hexdigest()[:16]


def findings_from(result, graph, impact_scores: dict[str, float]) -> list[Finding]:
    """Findings from an already-computed analysis + graph (no re-analysis, so the caller controls root)."""
    findings: dict[str, Finding] = {}
    detectors = result.detectors()
    patterns = {(h.where): h.pattern for h in attack.recognize(graph, result)}
    for sink, paths in attack.attacker_paths(graph).items():
        path = paths[0]  # shortest anyone->sink path
        labels = [graph.nodes[n].label for n in path.nodes]
        fn_nodes = [graph.nodes[n] for n in path.nodes if n.startswith("fn:")]
        entry = fn_nodes[0].label if fn_nodes else labels[0]
        pattern = next((p for w, p in patterns.items() if w in labels), None)
        impact, evidence = _worst_impact(labels, detectors)
        fid = _stable_id(labels)
        findings[fid] = Finding(
            stable_id=fid, entry=entry, sink=graph.nodes[sink].label, pattern=pattern,
            max_impact=impact, severity_score=impact_scores.get(impact, 0.0),
            evidence=evidence, path=labels)
    return sorted(findings.values(), key=lambda f: (-f.severity_score, f.entry))


def scan_source(sol_files: list[Path], impact_scores: dict[str, float]) -> list[Finding]:
    merged: dict[str, Finding] = {}
    for file in sol_files:
        result = analyze(file, root=file.parent)
        graph = build(result)  # static only: no DeployedContext, no chain
        for f in findings_from(result, graph, impact_scores):
            merged[f.stable_id] = f
    return sorted(merged.values(), key=lambda f: (-f.severity_score, f.entry))


def _worst_impact(path_labels: list[str], detectors) -> tuple[str, list[str]]:
    on_path = []
    for d in detectors:
        if d.contract and d.function and f"{d.contract}.{_bare(d.function)}" in \
                {lbl.split("(")[0] for lbl in path_labels}:
            on_path.append(d)
    if not on_path:
        return "None", []
    worst = max(on_path, key=lambda d: _IMPACT_ORDER.get(d.slither_impact, 0))
    evidence = [f"slither:{d.name}({d.slither_impact})@{d.file}:{d.lines}" for d in on_path]
    return worst.slither_impact, evidence


def collect_sol(path: Path) -> list[Path]:
    path = Path(path)
    return [path] if path.is_file() else sorted(path.rglob("*.sol"))


def write_baseline(path: Path, findings: list[Finding], version: str) -> None:
    Path(path).write_text(json.dumps(
        {"version": version, "findings": [asdict(f) for f in findings]}, indent=2))


def read_baseline(path: Path) -> list[Finding]:
    data = json.loads(Path(path).read_text())
    return [Finding(**f) for f in data["findings"]]
