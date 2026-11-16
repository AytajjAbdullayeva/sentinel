"""Group 4 checkpoint: build the attack graph for 3 reconstructed exploit patterns; show topology."""

import json
from pathlib import Path

from sentinel.chain.anvil import Anvil
from sentinel.graph import attack, reconstruct
from sentinel.graph.builder import build
from sentinel.graph.model import EdgeType

OUT = Path(__file__).resolve().parent.parent / "out"


def _show_path(g, p):
    parts = [g.nodes[p.nodes[0]].label]
    for e in p.edges:
        parts.append(f"--{e.type.value}-->")
        parts.append(g.nodes[e.dst].label)
    return " ".join(parts)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    report = {}
    with Anvil() as node:
        for r in reconstruct.all_reconstructions(node.w3):
            g = build(r.analysis, r.context)
            print(f"\n{'=' * 78}\n{r.name}: {r.addresses}")
            print(f"  graph: {len(g.nodes)} nodes, {len(g.edges)} edges; "
                  f"deps={sum(e.type==EdgeType.DEPENDS_ON for e in g.edges.values())} "
                  f"transfers={sum(e.type==EdgeType.TRANSFERS for e in g.edges.values())} "
                  f"controls={sum(e.type==EdgeType.CONTROLS for e in g.edges.values())}")
            hits = attack.recognize(g, r.analysis)
            for h in hits:
                print(f"  [pattern] {h.pattern} @ {h.where}")
                for ev in h.evidence:
                    print(f"            - {ev}")
                if h.path:
                    print(f"            path: {_show_path(g, h.path)}")
            ap = attack.attacker_paths(g)
            for sink, paths in ap.items():
                print(f"  attacker -> {g.nodes[sink].label}: {len(paths)} path(s)")
                for p in paths:
                    print(f"      cost {p.cost:.0f}: {_show_path(g, p)}")
            report[r.name] = {
                "addresses": r.addresses,
                "nodes": len(g.nodes), "edges": len(g.edges),
                "patterns": [{"pattern": h.pattern, "where": h.where, "evidence": h.evidence} for h in hits],
                "graph": g.to_dict(),
            }
    (OUT / "group4.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"\nwrote {OUT / 'group4.json'}")


if __name__ == "__main__":
    main()
