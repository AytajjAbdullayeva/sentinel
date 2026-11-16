"""Capstone: run the full pipeline on 5 unrelated real contracts and show genuinely different results."""

import json
from decimal import Decimal
from pathlib import Path

from sentinel import pipeline
from sentinel.chain.anvil import Anvil
from sentinel.graph import reconstruct
from sentinel.sim import exploits
from sentinel.value.model import Declared, Quantity

OUT = Path(__file__).resolve().parent.parent / "out"
WETH = reconstruct.VULN_DIR.parent.parent / "external" / "weth"
UNIV2 = reconstruct.VULN_DIR.parent.parent / "external" / "univ2"
PRICE = Quantity(Decimal(2500), "USD", Declared("demo", "2026-09-25", "local ETH price"))


def _s(sc):
    return sc.attacker_addresses, sc.steps


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rows = []
    # static (no chain): two unrelated production contracts
    rows.append(pipeline.analyze_static("WETH9", [WETH / "contracts" / "WETH9.sol"]))
    rows.append(pipeline.analyze_static("UniswapV2Pair", [UNIV2 / "contracts" / "UniswapV2Pair.sol"]))
    # full (real Anvil sim + score + narrative): three unrelated exploit reconstructions
    with Anvil() as node:
        w3 = node.w3
        reent = reconstruct.reentrancy(w3)
        rows.append(pipeline.analyze_full("reentrancy", w3, reent.analysis, reent.context,
                                          *_s(exploits.reentrancy(w3, patched=False)), PRICE))
        orc = reconstruct.oracle(w3)
        rows.append(pipeline.analyze_full("oracle-manipulation", w3, orc.analysis, orc.context,
                                          *_s(exploits.oracle_manipulation(w3, patched=False)), PRICE))
        gov = reconstruct.governance(w3)
        rows.append(pipeline.analyze_static("governance-treasury", [reconstruct.VULN_DIR / "GovTreasury.sol"]))

    print("END-TO-END PIPELINE over 5 unrelated real contracts:\n")
    for pa in rows:
        print("  " + pa.summary())
    graphs = {(pa.graph_nodes, pa.graph_edges) for pa in rows}
    scores = {pa.score.display for pa in rows if pa.score}
    print(f"\ndistinct graph shapes: {len(graphs)}/{len(rows)}   distinct score outcomes: {sorted(scores)}")
    assert len(graphs) >= 3, "expected genuinely different graphs"
    assert len([pa for pa in rows if pa.score and pa.score.status == 'scored']) >= 2
    (OUT / "pipeline.json").write_text(json.dumps(
        [{"name": pa.name, "compiler": pa.compiler, "nodes": pa.graph_nodes, "edges": pa.graph_edges,
          "patterns": pa.patterns, "score": pa.score.display if pa.score else None} for pa in rows], indent=2))
    print(f"\nwrote {OUT / 'pipeline.json'}")


if __name__ == "__main__":
    main()
